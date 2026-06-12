module.exports = {
  apps: [
    {
      name: 'job-ai',
      script: './venv/bin/gunicorn',
      args: '-w 1 -b 0.0.0.0:5000 --timeout 300 app:app',
      cwd: '/opt/job-ai',
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: '/root/.pm2/logs/job-ai-error.log',
      out_file: '/root/.pm2/logs/job-ai-out.log',
      merge_logs: false,
      kill_timeout: 5000,
      listen_timeout: 10000,
      min_uptime: '10s'
    }
  ]
};
