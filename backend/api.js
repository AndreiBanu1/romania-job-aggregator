const express = require('express')
const { exec } = require('child_process')
const fs = require('fs')

const app = express()
const PORT = 3000

app.use(require('cors')())
app.use(express.json())

const path = require('path')
const citiesPath = path.join(__dirname, 'scrappers', 'romanian_cities.json')
const cities = JSON.parse(fs.readFileSync(citiesPath, 'utf8'))

app.post('/jobs', (req, res) => {
  const { title, city } = req.body

  const scriptPath = path.join(__dirname, 'scrappers', 'aggregate_scrappers.py')
  const outputPath = path.join(__dirname, '..', 'job-results', 'temp-aggregated.json')

  exec(
    `python3 "${scriptPath}" --title "${title}" --location "${city}" --page-size 25 --max-pages 0 --output "${outputPath}"`,
    (err, stdout, stderr) => {
      if (err) return res.status(500).json({ error: stderr })

      fs.readFile(outputPath, 'utf8', (err, data) => {
        if (err) return res.status(500).json({ error: 'Failed to read JSON' })
        res.json(JSON.parse(data))
      })
    },
  )
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
