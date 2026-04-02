const express = require('express');
const { exec } = require('child_process');
const fs = require('fs');

const app = express();
const PORT = 3000;

app.get('/jobs', (req, res) => {
  const { title, location } = req.query;

  // Run the Python scraper
  exec(`python3 backend/run-all-scrapers.py --title "${title}" --location "${location}" --page-size 25 --max-pages 0 --prefix temp`, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({ error: stderr });
    }

    // Read the resulting JSON
    const filePath = 'job-results/temp-aggregated.json';
    fs.readFile(filePath, 'utf8', (err, data) => {
      if (err) return res.status(500).json({ error: 'Failed to read JSON' });
      res.json(JSON.parse(data));
    });
  });
});

app.listen(PORT, () => console.log(`API running on http://localhost:${PORT}`));