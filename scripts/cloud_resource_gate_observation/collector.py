from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.cloud_resource_gate_observation.command import run_command, shell_quote
from scripts.cloud_resource_gate_observation.constants import HTTP_PATHS
from scripts.cloud_resource_gate_observation.parsers import collect_from_sections


def build_remote_script(project_dir: str, app_base_url: str, journal_since: str, docker_logs_since: str) -> str:
    http_paths = " ".join(shell_quote(path) for path in HTTP_PATHS)
    mysql = (
        "sudo docker compose -f docker-compose.mysql.yml exec -T mysql "
        'mysql -N -B -uroot -p"$MYSQL_ROOT_PASSWORD" -D "$MYSQL_DATABASE"'
    )
    return f"""
set -u
cd {shell_quote(project_dir)}
printf '__SECTION__:date\\n'
date
printf '__SECTION__:uptime\\n'
uptime
printf '__SECTION__:free\\n'
free -m || true
printf '__SECTION__:df_root\\n'
df -h / || true
printf '__SECTION__:df_inode_root\\n'
df -ih / || true
printf '__SECTION__:compose_ps\\n'
sudo docker compose -f docker-compose.mysql.yml ps --format '{{{{.Name}}}}\\t{{{{.Status}}}}' || true
printf '__SECTION__:docker_stats\\n'
sudo docker stats --no-stream --format '{{{{.Name}}}}\\t{{{{.CPUPerc}}}}\\t{{{{.MemUsage}}}}\\t{{{{.MemPerc}}}}' || true
printf '__SECTION__:docker_system_df\\n'
sudo docker system df || true
printf '__SECTION__:http\\n'
for path in {http_paths}; do
  output="$(curl -sS -o /dev/null -w '%{{http_code}} %{{time_total}}' --max-time 20 {shell_quote(app_base_url)}"$path" 2>&1)"
  rc=$?
  printf '%s\\t%s\\t%s\\n' "$path" "$rc" "$output"
done
printf '__SECTION__:oom_logs\\n'
sudo journalctl -k --since {shell_quote(journal_since)} --no-pager 2>/dev/null | egrep -i 'out of memory|oom|killed process' | tail -80 || true
printf '__SECTION__:mysql_status\\n'
if test -f .env; then
  set -a
  . ./.env
  set +a
fi
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SHOW GLOBAL STATUS LIKE 'Threads_%'; SHOW GLOBAL STATUS LIKE 'Slow_queries';" 2>/dev/null || true
fi
printf '__SECTION__:mysql_variables\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SHOW VARIABLES LIKE 'max_connections'; SHOW VARIABLES LIKE 'innodb_buffer_pool_size';" 2>/dev/null || true
fi
printf '__SECTION__:mysql_table_space\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024,2) AS mb FROM information_schema.tables WHERE table_schema NOT IN ('mysql','performance_schema','information_schema','sys') GROUP BY table_schema ORDER BY mb DESC;" 2>/dev/null || true
fi
printf '__SECTION__:task_summary\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SELECT task_type,status,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE created_at >= NOW() - INTERVAL 2 HOUR GROUP BY task_type,status ORDER BY cnt DESC, task_type LIMIT 80;" 2>/dev/null || true
fi
printf '__SECTION__:task_nonterminal\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SELECT status,task_type,priority,COUNT(*) cnt,MIN(created_at) oldest,MAX(updated_at) latest FROM runtime_tasks WHERE status IN ('queued','running') GROUP BY status,task_type,priority ORDER BY FIELD(status,'running','queued'),priority DESC,cnt DESC LIMIT 80;" 2>/dev/null || true
fi
printf '__SECTION__:heartbeats\\n'
if test -n "${{MYSQL_ROOT_PASSWORD:-}}" && test -n "${{MYSQL_DATABASE:-}}"; then
  {mysql} -e "SELECT \\`key\\`,updated_at,LEFT(value,220) value_prefix FROM system_settings WHERE \\`key\\` IN ('platform_component.heartbeat.runtime-scheduler','platform_component.heartbeat.runtime-worker','runtime_worker.heartbeat') ORDER BY \\`key\\`;" 2>/dev/null || true
fi
printf '__SECTION__:worker_logs\\n'
sudo docker logs --since {shell_quote(docker_logs_since)} tquant-runtime-worker-mysql 2>&1 | egrep -i 'recycle|rss|oom|killed|error|exception' | tail -120 || true
printf '__SECTION__:scheduler_logs\\n'
sudo docker logs --since {shell_quote(docker_logs_since)} tquant-runtime-scheduler-mysql 2>&1 | egrep -i 'provider|circuit|timeout|failed|error|exception' | tail -160 || true
"""


def collect_remote(
    host: str,
    user: str,
    ssh_key: Path | None,
    project_dir: str,
    app_base_url: str,
    journal_since: str,
    docker_logs_since: str,
) -> dict[str, Any]:
    remote_script = build_remote_script(project_dir, app_base_url, journal_since, docker_logs_since)
    command = ["ssh", "-o", "StrictHostKeyChecking=no", f"{user}@{host}", remote_script]
    if ssh_key:
        command[1:1] = ["-i", str(ssh_key)]
    result = run_command(command, timeout=180)
    sections: dict[str, str] = {}
    current: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("__SECTION__:"):
            current = line.split(":", 1)[1]
            sections[current] = ""
        elif current:
            sections[current] += line + "\n"
    report = collect_from_sections(sections)
    report["source"] = {
        "remote_host": host,
        "remote_user": user,
        "project_dir": project_dir,
        "app_base_url": app_base_url,
        "journal_since": journal_since,
        "docker_logs_since": docker_logs_since,
    }
    report["commands"] = {
        "ssh": {
            "command": "ssh <redacted>",
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }
    }
    return report
