#!/bin/bash
# Script tự động chạy kiểm thử trên môi trường Windows (Wine Docker)
# Định dạng xuống dòng: LF (sử dụng trên Linux host để chạy docker command)

IMAGE_NAME="tobix/pywine:3.12"
CONTAINER_WORK_DIR="/app"

echo "=========================================================="
echo " Bắt đầu quy trình kiểm thử Windows trên Wine Docker"
echo "=========================================================="

# 1. Chạy container docker để thực hiện quá trình cài đặt và test
docker run --rm \
  -e QT_QPA_PLATFORM=offscreen \
  -e WINEDEBUG=-all \
  -e PYTHONIOENCODING=utf-8 \
  -e PYTHONUTF8=1 \
  -v "$(pwd):${CONTAINER_WORK_DIR}" \
  -v "$(pwd)/.pip_cache:/root/.cache/pip" \
  -w "${CONTAINER_WORK_DIR}" \
  "${IMAGE_NAME}" \
  bash -c '
    echo "----------------------------------------------------"
    echo "1. Khởi tạo cấu hình Wine Prefix..."
    echo "----------------------------------------------------"
    . /opt/mkuserwineprefix
    
    # Đảm bảo wineboot chạy xong
    wineboot -u
    
    # Cấu hình Wine chạy ở chế độ Windows 10
    winecfg /v win10
    
    echo "----------------------------------------------------"
    echo "2. Cài đặt dependencies offline cho Windows từ .pip_wheels..."
    echo "----------------------------------------------------"
    wine pip install --no-index --find-links=.pip_wheels -r requirements.txt
    
    echo "----------------------------------------------------"
    echo "3. Thực thi 12 Trigger Scripts kiểm chứng lỗi..."
    echo "----------------------------------------------------"
    python_files=(
      "scratch/trigger_tokenization_bug.py"
      "scratch/trigger_drift_bug.py"
      "scratch/trigger_filesystem_bugs.py"
      "scratch/trigger_git_robustness.py"
      "scratch/trigger_mcp_robustness.py"
      "scratch/trigger_memory_race.py"
      "scratch/trigger_tokenization_race.py"
      "scratch/trigger_cancellation_bug.py"
      "scratch/trigger_watcher_lifecycle.py"
      "scratch/trigger_worker_gc.py"
      "scratch/trigger_diff_bug.py"
      "scratch/trigger_copy_diff.py"
      "scratch/trigger_persistence_bugs.py"
      "scratch/trigger_ai_prompt_bugs.py"
      "scratch/trigger_workflow_bugs.py"
      "scratch/trigger_codemap_bugs.py"
      "scratch/trigger_codemap_oom.py"
    )
    
    failed_scripts=()
    passed_scripts=()
    
    for script in "${python_files[@]}"; do
      echo ""
      echo ">>> Đang chạy: wine python -X utf8 $script"
      wine python -X utf8 "$script"
      status=$?
      if [ $status -ne 0 ]; then
        echo ">>> KẾT QUẢ: THẤT BẠI (Exit code: $status)"
        failed_scripts+=("$script")
      else
        echo ">>> KẾT QUẢ: PASS"
        passed_scripts+=("$script")
      fi
      echo "----------------------------------------------------"
    done
    
    echo ""
    echo "----------------------------------------------------"
    echo "4. Thực thi Pytest Unit Tests..."
    echo "----------------------------------------------------"
    wine pytest tests/ -v
    pytest_status=$?
    
    echo ""
    echo "===================================================="
    echo "             TỔNG HỢP KẾT QUẢ KIỂM THỬ"
    echo "===================================================="
    echo "Số lượng Trigger Scripts PASS: ${#passed_scripts[@]}/12"
    
    if [ ${#failed_scripts[@]} -ne 0 ]; then
      echo "Danh sách Trigger Scripts THẤT BẠI:"
      for f in "${failed_scripts[@]}"; do
        echo "  - $f"
      done
    else
      echo "Tất cả các Trigger Scripts đều PASS trên Windows!"
    fi
    
    echo "Trạng thái Pytest suite: (Exit code: $pytest_status)"
    if [ $pytest_status -eq 0 ]; then
      echo "Pytest: 100% SUCCESS!"
    else
      echo "Pytest: CÓ LỖI XẢY RA!"
    fi
    
    if [ ${#failed_scripts[@]} -ne 0 ] || [ $pytest_status -ne 0 ]; then
      exit 1
    fi
    exit 0
  '
