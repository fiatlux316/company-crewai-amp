import os
import zipfile
import shutil
import tempfile
import ast
import json
import re

def sanitize_crew_id(name):
    # 특수문자 및 공백 제거, 소문자 변환
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', name.replace('-', '_'))
    return sanitized.lower()

def extract_default_inputs(main_py_path):
    if not os.path.exists(main_py_path):
        return {}
    try:
        with open(main_py_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            # run() 함수 정의 탐색
            if isinstance(node, ast.FunctionDef) and node.name == 'run':
                # 함수 몸체 내에서 inputs 할당 식 탐색
                for body_node in node.body:
                    if isinstance(body_node, ast.Assign):
                        for target in body_node.targets:
                            if isinstance(target, ast.Name) and target.id == 'inputs':
                                # 리터럴 딕셔너리 안전 평가
                                try:
                                    return ast.literal_eval(body_node.value)
                                except Exception as e:
                                    print(f"Failed to literal_eval inputs: {e}")
                                    pass
    except Exception as e:
        print(f"Error parsing AST from main.py: {e}")
    return {}

def find_main_py(directory):
    for root, dirs, files in os.walk(directory):
        # 가상환경, 빌드 캐시, git 등의 폴더 탐색 제외 (os.walk의 dirs를 직접 필터링)
        dirs[:] = [d for d in dirs if d not in ('.venv', 'venv', '__pycache__', '.git', 'tests', 'node_modules', '.venv-docker')]
        if "main.py" in files:
            return os.path.join(root, "main.py")
    return None

def process_crew_zip(zip_file_path, filename, overwrite=False):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crews_dir = os.path.join(base_dir, "crews")
    os.makedirs(crews_dir, exist_ok=True)
    
    # 1. 임시 디렉토리에 압축 풀기
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
            
        # 2. 업로드 파일의 최상위 구조 분석
        items = [i for i in os.listdir(temp_dir) if not i.startswith(('.', '__'))]
        if not items:
            raise ValueError("The uploaded ZIP file is empty.")
            
        # 압축파일 내부에 단일 최상위 폴더가 존재하는 구조인지 판별
        first_item_path = os.path.join(temp_dir, items[0])
        if len(items) == 1 and os.path.isdir(first_item_path):
            extracted_crew_name = items[0]
            source_path = first_item_path
        else:
            extracted_crew_name = os.path.splitext(filename)[0]
            source_path = temp_dir
            
        crew_id = sanitize_crew_id(extracted_crew_name)
        if not crew_id:
            crew_id = "uploaded_crew"
            
        # 중복 체크: 이미 존재하고 overwrite가 False면 중복 예외 발생
        target_path = os.path.join(crews_dir, crew_id)
        if os.path.exists(target_path) and not overwrite:
            raise FileExistsError(f"Crew '{crew_id}' already exists.")
            
        # 3. main.py 탐색 및 AST 분석을 통한 inputs 파라미터 추출
        main_py = find_main_py(source_path)
        default_inputs = {}
        if main_py:
            default_inputs = extract_default_inputs(main_py)
            
        # 4. 대상 crews/ 디렉토리에 복사
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
            
        shutil.copytree(source_path, target_path)
        
        # 5. default_inputs.json 파일 저장
        inputs_path = os.path.join(target_path, "default_inputs.json")
        with open(inputs_path, 'w', encoding='utf-8') as f:
            json.dump(default_inputs, f, ensure_ascii=False, indent=2)
            
        return {
            "crew_id": crew_id,
            "display_name": " ".join(x.capitalize() for x in crew_id.split("_")),
            "default_inputs": default_inputs
        }
