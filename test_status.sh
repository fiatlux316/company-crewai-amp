task_id=$1

# task_id 가 없으면 에러 메세지, 사용법 출력
if [ -z "$task_id" ]; then
    echo "Error: Task ID is required."
    echo "Usage: ./test_status.sh <task_id>"
    exit 1
fi

curl -X GET http://localhost:8000/api/v1/tasks/$task_id \
  -H "Authorization: Bearer super-secret-company-key"