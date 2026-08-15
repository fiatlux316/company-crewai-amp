curl -X POST http://localhost:8000/api/v1/crews/monitoring/kickoff \
  -H "Authorization: Bearer super-secret-company-key" \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"recipient_email": "jck@shinsegae.com", "time_range": "last 1 hour", "datadog_query": "service:erody-bo-backend-20 @http.status_code:[400 TO 599]", "output_path": "./output/output.md", "limit": "5"}}'