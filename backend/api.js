const express = require('express')
const cors = require('cors')
const { spawn } = require('child_process')
const fs = require('fs')
const os = require('os')
const crypto = require('crypto')
const path = require('path')

const PORT = Number(process.env.PORT) || 3000

// Comma-separated list of origins allowed to call the API. Defaults to the
// Angular dev server; an open CORS policy would let any site drive scrapes.
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS || 'http://localhost:4200')
  .split(',')
  .map((origin) => origin.trim())
  .filter(Boolean)

// A full search spawns ~4 Python processes and runs for 15-30s. Without a cap,
// a handful of concurrent requests can exhaust a small machine.
const MAX_CONCURRENT_SEARCHES = Number(process.env.MAX_CONCURRENT_SEARCHES) || 2
const SEARCH_TIMEOUT_MS = Number(process.env.SEARCH_TIMEOUT_MS) || 5 * 60 * 1000
const DESCRIPTION_TIMEOUT_MS = Number(process.env.DESCRIPTION_TIMEOUT_MS) || 60 * 1000

const MAX_TITLE_LENGTH = 100
const MAX_CITY_LENGTH = 60
const MAX_HREF_LENGTH = 2048

const app = express()
app.disable('x-powered-by')
app.use(cors({ origin: ALLOWED_ORIGINS }))
app.use(express.json({ limit: '10kb' }))

const citiesPath = path.join(__dirname, 'scrappers', 'romanian_cities.json')
const cities = JSON.parse(fs.readFileSync(citiesPath, 'utf8'))

const projectRoot = path.join(__dirname, '..')

// Prefer the project virtualenv: the scrapers need requests/bs4, which the
// system python3 does not have.
function resolvePython() {
  const venvPython = path.join(projectRoot, '.venv', 'bin', 'python')
  return fs.existsSync(venvPython) ? venvPython : 'python3'
}

// Descriptions are paced at roughly one request per 1.5s per host, so asking
// for all of them turns a 9s search into minutes. Opt-in, and capped.
const DEFAULT_DESC_LIMIT = 25
const MAX_DESC_LIMIT = 100

function resolveDescLimit(value) {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) return DEFAULT_DESC_LIMIT
  return Math.min(parsed, MAX_DESC_LIMIT)
}

function isNonEmptyString(value, maxLength) {
  return typeof value === 'string' && value.trim() !== '' && value.length <= maxLength
}

/**
 * Runs a Python script with a hard timeout, and kills it if the client goes
 * away first, so abandoned requests do not keep scraping in the background.
 * Resolves with { code, stdout, stderr, reason } where reason is
 * 'exit' | 'timeout' | 'aborted' | 'spawn-error'.
 */
function runPython(args, { timeoutMs, res }) {
  return new Promise((resolve) => {
    // Own process group, so a kill also reaches the per-source scrapers the
    // aggregator spawns; killing only the parent would orphan them.
    const child = spawn(resolvePython(), args, { cwd: projectRoot, detached: true })
    const killTree = () => {
      try {
        process.kill(-child.pid, 'SIGKILL')
      } catch {
        child.kill('SIGKILL')
      }
    }
    let stdout = ''
    let stderr = ''
    let reason = 'exit'
    let settled = false

    const finish = (result) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      res.off('close', onClientClose)
      resolve(result)
    }

    const timer = setTimeout(() => {
      reason = 'timeout'
      killTree()
    }, timeoutMs)

    // The response emits 'close' when the connection goes away. (The
    // request's own 'close' fires as soon as its body has been read, so it
    // cannot signal a disconnect.) Only an unfinished response means the
    // client gave up.
    const onClientClose = () => {
      if (!res.writableEnded) {
        reason = 'aborted'
        killTree()
      }
    }
    res.on('close', onClientClose)

    child.stdout.on('data', (chunk) => {
      stdout += chunk
    })
    child.stderr.on('data', (chunk) => {
      stderr += chunk
    })

    child.on('error', (err) => {
      finish({ code: null, stdout, stderr: err.message, reason: 'spawn-error' })
    })
    child.on('close', (code) => {
      finish({ code, stdout, stderr, reason })
    })
  })
}

/** Server-side detail for the logs; never sent to the client. */
function logFailure(label, result) {
  console.error(
    `[${label}] failed (reason=${result.reason}, code=${result.code})`,
    result.stderr.trim().slice(-2000),
  )
}

let activeSearches = 0

app.post('/jobs', async (req, res) => {
  const { title, city, mode, descriptions, descLimit } = req.body ?? {}

  if (!isNonEmptyString(title, MAX_TITLE_LENGTH)) {
    return res.status(400).json({ error: `title is required (max ${MAX_TITLE_LENGTH} characters)` })
  }
  if (!isNonEmptyString(city, MAX_CITY_LENGTH)) {
    return res.status(400).json({ error: `city is required (max ${MAX_CITY_LENGTH} characters)` })
  }

  if (activeSearches >= MAX_CONCURRENT_SEARCHES) {
    res.set('Retry-After', '30')
    return res.status(503).json({ error: 'The server is busy with other searches. Try again in a moment.' })
  }

  const filterMode = ['strict', 'loose', 'none'].includes(mode) ? mode : 'loose'

  // Unique per request: a shared temp file lets concurrent searches overwrite
  // each other's results.
  const outputPath = path.join(os.tmpdir(), `jobs-${crypto.randomUUID()}.json`)

  const scriptArgs = [
    path.join(__dirname, 'scrappers', 'aggregate_scrappers.py'),
    '--title', title.trim(),
    '--location', city.trim(),
    '--page-size', '25',
    '--max-pages', '0',
    '--mode', filterMode,
    '--output', outputPath,
  ]
  if (descriptions === true) {
    scriptArgs.push('--descriptions', '--desc-limit', String(resolveDescLimit(descLimit)))
  }

  activeSearches += 1
  try {
    // Argument array, no shell: user input can never be interpreted as a command.
    const result = await runPython(scriptArgs, { timeoutMs: SEARCH_TIMEOUT_MS, res })

    if (result.reason === 'aborted') return
    if (result.reason === 'timeout') {
      logFailure('jobs', result)
      return res.status(504).json({ error: 'The search took too long. Try a narrower query.' })
    }
    if (result.code !== 0) {
      logFailure('jobs', result)
      return res.status(500).json({ error: 'The search failed. Please try again.' })
    }

    const data = await fs.promises.readFile(outputPath, 'utf8')
    res.json(JSON.parse(data))
  } catch (err) {
    console.error('[jobs] could not read scraper output', err)
    if (!res.headersSent) res.status(500).json({ error: 'The search failed. Please try again.' })
  } finally {
    activeSearches -= 1
    fs.promises.unlink(outputPath).catch(() => {})
  }
})

// One description, fetched when the user actually opens a job. Keeps the
// search itself fast while still making descriptions reachable in the UI.
app.post('/job-description', async (req, res) => {
  const { href } = req.body ?? {}

  if (!isNonEmptyString(href, MAX_HREF_LENGTH)) {
    return res.status(400).json({ error: 'href is required' })
  }

  const scriptPath = path.join(__dirname, 'scrappers', 'fetch_description.py')
  const result = await runPython([scriptPath, '--url', href], {
    timeoutMs: DESCRIPTION_TIMEOUT_MS,
    res,
  })

  if (result.reason === 'aborted') return
  if (result.reason === 'timeout') {
    logFailure('job-description', result)
    return res.status(504).json({ error: 'Fetching the description took too long.' })
  }

  let payload
  try {
    payload = JSON.parse(result.stdout)
  } catch {
    logFailure('job-description', result)
    return res.status(500).json({ error: 'Could not fetch the description.' })
  }

  // Exit code 2 means the host was rejected, which is the caller's fault.
  if (result.code === 2) return res.status(400).json(payload)
  if (result.code !== 0) {
    logFailure('job-description', result)
    return res.status(500).json({ error: 'Could not fetch the description.' })
  }

  res.json(payload)
})

app.post('/jobs-mock', async (req, res) => {
  try {
    const data = await fs.promises.readFile(
      path.join(__dirname, 'jobs_response_example.json'),
      'utf8',
    )
    res.json(JSON.parse(data))
  } catch (err) {
    console.error('[jobs-mock] could not read fixture', err)
    res.status(500).json({ error: 'Failed to read mock JSON' })
  }
})

app.get('/cities', (req, res) => {
  res.json(cities)
})

app.get('/health', (req, res) => {
  res.json({ status: 'ok', activeSearches })
})

app.listen(PORT, () => console.log(`API running on http://localhost:${PORT}`))
