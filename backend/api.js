const express = require('express')
const { spawn } = require('child_process')
const fs = require('fs')
const os = require('os')
const crypto = require('crypto')

const app = express()
const PORT = 3000

app.use(require('cors')())
app.use(express.json())

const path = require('path')
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

app.post('/jobs', (req, res) => {
  const { title, city, mode, descriptions, descLimit } = req.body

  if (typeof title !== 'string' || !title.trim()) {
    return res.status(400).json({ error: 'title is required' })
  }
  if (typeof city !== 'string' || !city.trim()) {
    return res.status(400).json({ error: 'city is required' })
  }

  const filterMode = ['strict', 'loose', 'none'].includes(mode) ? mode : 'loose'
  const wantDescriptions = descriptions === true

  const scriptPath = path.join(__dirname, 'scrappers', 'aggregate_scrappers.py')
  // Unique per request: a shared temp file lets concurrent searches overwrite
  // each other's results.
  const outputPath = path.join(
    os.tmpdir(),
    `jobs-${crypto.randomUUID()}.json`,
  )

  const scriptArgs = [
    scriptPath,
    '--title',
    title,
    '--location',
    city,
    '--page-size',
    '25',
    '--max-pages',
    '0',
    '--mode',
    filterMode,
    '--output',
    outputPath,
  ]

  if (wantDescriptions) {
    scriptArgs.push('--descriptions', '--desc-limit', String(resolveDescLimit(descLimit)))
  }

  // Argument array, no shell: user input can never be interpreted as a command.
  const child = spawn(resolvePython(), scriptArgs, { cwd: projectRoot })

  let stderr = ''
  child.stderr.on('data', (chunk) => {
    stderr += chunk
  })
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))

  const cleanup = () => fs.promises.unlink(outputPath).catch(() => {})

  child.on('error', (err) => {
    res.status(500).json({ error: `Failed to start scraper: ${err.message}` })
  })

  child.on('close', (code) => {
    if (code !== 0) {
      cleanup()
      return res.status(500).json({ error: stderr || `Scraper exited with code ${code}` })
    }

    fs.readFile(outputPath, 'utf8', (err, data) => {
      cleanup()
      if (err) return res.status(500).json({ error: 'Failed to read JSON' })
      try {
        res.json(JSON.parse(data))
      } catch {
        res.status(500).json({ error: 'Scraper produced invalid JSON' })
      }
    })
  })
})

// One description, fetched when the user actually opens a job. Keeps the
// search itself fast while still making descriptions reachable in the UI.
app.post('/job-description', (req, res) => {
  const { href } = req.body

  if (typeof href !== 'string' || !href.trim()) {
    return res.status(400).json({ error: 'href is required' })
  }

  const scriptPath = path.join(__dirname, 'scrappers', 'fetch_description.py')
  const child = spawn(resolvePython(), [scriptPath, '--url', href], {
    cwd: projectRoot,
  })

  let stdout = ''
  let stderr = ''
  child.stdout.on('data', (chunk) => {
    stdout += chunk
  })
  child.stderr.on('data', (chunk) => {
    stderr += chunk
  })

  child.on('error', (err) => {
    res.status(500).json({ error: `Failed to start fetcher: ${err.message}` })
  })

  child.on('close', (code) => {
    let payload
    try {
      payload = JSON.parse(stdout)
    } catch {
      return res
        .status(500)
        .json({ error: stderr.trim() || 'Fetcher produced invalid JSON' })
    }

    // Exit code 2 means the host was rejected, which is the caller's fault.
    if (code === 2) return res.status(400).json(payload)
    if (code !== 0) {
      return res.status(500).json({ error: payload.error || `Fetcher exited with code ${code}` })
    }

    res.json(payload)
  })
})

app.post('/jobs-mock', (req, res) => {
  const mockPath = path.join(__dirname, 'jobs_response_example.json')
  fs.readFile(mockPath, 'utf8', (err, data) => {
    if (err) return res.status(500).json({ error: 'Failed to read mock JSON' })
    res.json(JSON.parse(data))
  })
})

app.get('/cities', (req, res) => {
  res.json(cities)
})

app.listen(PORT, () => console.log(`API running on http://localhost:${PORT}`))
