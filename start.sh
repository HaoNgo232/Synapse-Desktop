#!/bin/bash

# Script khởi động ứng dụng Overwrite Desktop
# Tự động kiểm tra và tạo virtual environment nếu cần

VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"

# Màu sắc cho output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Synapse Desktop Startup Script ===${NC}\n"

# Kiểm tra xem virtual environment có tồn tại không
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment chưa tồn tại tại: $VENV_DIR${NC}"
    read -p "Bạn có muốn tạo virtual environment không? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Đang tạo virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Lỗi: Không thể tạo virtual environment!${NC}"
            echo -e "${YELLOW}Vui lòng kiểm tra xem python3-venv đã được cài đặt chưa.${NC}"
            echo -e "${YELLOW}Chạy: sudo apt install python3-venv${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Virtual environment đã được tạo thành công!${NC}\n"
    else
        echo -e "${RED}Không thể tiếp tục mà không có virtual environment.${NC}"
        exit 1
    fi
fi

# Kích hoạt virtual environment
echo -e "${GREEN}Đang kích hoạt virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo -e "${RED}Lỗi: Không thể kích hoạt virtual environment!${NC}"
    exit 1
fi

# Kiểm tra xem đã vào virtual environment chưa
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Lỗi: Virtual environment chưa được kích hoạt!${NC}"
    echo -e "${YELLOW}Biến môi trường VIRTUAL_ENV không được thiết lập.${NC}"
    echo -e "${RED}Không thể tiếp tục. Vui lòng kiểm tra lại cấu hình.${NC}"
    exit 1
fi

echo -e "${GREEN}Virtual environment đã được kích hoạt: $VIRTUAL_ENV${NC}\n"

# Kiểm tra file requirements.txt
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Cảnh báo: Không tìm thấy file $REQUIREMENTS_FILE${NC}"
    echo -e "${YELLOW}Bỏ qua bước cài đặt dependencies.${NC}\n"
else
    # Cài đặt dependencies
    echo -e "${GREEN}Đang cài đặt dependencies từ $REQUIREMENTS_FILE...${NC}"
    pip install -r "$REQUIREMENTS_FILE"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Lỗi: Không thể cài đặt dependencies!${NC}"
        echo -e "${YELLOW}Vui lòng kiểm tra file $REQUIREMENTS_FILE và kết nối internet.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Dependencies đã được cài đặt thành công!${NC}\n"
fi

# Kiểm tra file main_window.py (PySide6)
if [ ! -f "main_window.py" ]; then
    echo -e "${RED}Lỗi: Không tìm thấy file main_window.py!${NC}"
    exit 1
fi

# Chạy ứng dụng với PySide6
echo -e "${GREEN}Đang khởi động ứng dụng (PySide6)...${NC}\n"
python3 main_window.py

# Lưu exit code của ứng dụng
APP_EXIT_CODE=$?

# Deactivate virtual environment khi thoát
deactivate 2>/dev/null

if [ $APP_EXIT_CODE -ne 0 ]; then
    echo -e "\n${RED}Ứng dụng đã thoát với mã lỗi: $APP_EXIT_CODE${NC}"
    exit $APP_EXIT_CODE
fi

echo -e "\n${GREEN}Ứng dụng đã thoát thành công.${NC}"