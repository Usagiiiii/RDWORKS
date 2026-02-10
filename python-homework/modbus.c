// modbus.c
#include "modbus.h"
#include <string.h>

//#include "hwy_usb2com.h"
#include "hwy_sd.h"

//#include "usbd_cdc.h"
//#include "usbd_cdc_if.h"

#include "hwy_usb2com.h"
#include "grbl.h"

// 3.5字符时间计算 (在9600波特率下)
#define MODBUS_TIMEOUT_MS 4

//static modbus_slave_t modbus_slave;

//void modbus_init(modbus_slave_t *slave, UART_HandleTypeDef *huart)
void modbus_init(modbus_slave_t *slave) {
    memset(slave, 0, sizeof(modbus_slave_t));
    //slave->huart = huart;
    slave->rx_index = 0;
    slave->last_rx_time = 0;

    // 初始化一些示例数据
    for (int i = 0; i < HOLDING_REGISTER_SIZE; i++) {
        slave->holding_register[i] = i;
    }
    for (int i = 0; i < INPUT_REGISTER_SIZE; i++) {
        slave->input_register[i] = i * 2;
    }

    // 启动UART接收
    //HAL_UART_Receive_IT(slave->huart, &slave->rx_buffer[slave->rx_index], 1);
}

// CRC16计算 (Modbus)
uint16_t modbus_crc16(uint8_t *data, uint16_t length) {
    uint16_t crc = 0xFFFF;

    for (uint16_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc = crc >> 1;
            }
        }
    }

    return crc;
}

// 构建异常响应
void build_exception_response(modbus_slave_t *slave, uint8_t function,
                              uint8_t exception_code) {
    uint8_t tx_data[5];
    uint16_t crc;

    tx_data[0] = MODBUS_SLAVE_ADDRESS;
    tx_data[1] = function | 0x80;  // 设置异常标志
    tx_data[2] = exception_code;

    crc = modbus_crc16(tx_data, 3);
    tx_data[3] = crc & 0xFF;
    tx_data[4] = (crc >> 8) & 0xFF;

    //HAL_UART_Transmit(slave->huart, tx_data, 5, 100);
    CDC_print_blocking((char*) tx_data);
}

// 处理读保持寄存器 (功能码 0x03)
void handle_read_holding_registers(modbus_slave_t *slave, uint8_t *data) {
    uint16_t starting_addr = (data[2] << 8) | data[3];
    uint16_t quantity = (data[4] << 8) | data[5];
    uint8_t tx_data[256];
    uint16_t crc;
    uint8_t tx_length;

    // 地址和数量检查
    if (starting_addr + quantity > HOLDING_REGISTER_SIZE) {
        build_exception_response(slave, MODBUS_READ_HOLDING_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS);
        return;
    }

    if (quantity < 1 || quantity > 125) {
        build_exception_response(slave, MODBUS_READ_HOLDING_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_VALUE);
        return;
    }

    // 构建响应
    tx_data[0] = MODBUS_SLAVE_ADDRESS;
    tx_data[1] = MODBUS_READ_HOLDING_REGISTERS;
    tx_data[2] = quantity * 2;  // 字节数

    for (uint16_t i = 0; i < quantity; i++) {
        tx_data[3 + i * 2] = (slave->holding_register[starting_addr + i] >> 8)
                             & 0xFF;
        tx_data[4 + i * 2] = slave->holding_register[starting_addr + i] & 0xFF;
    }

    tx_length = 3 + quantity * 2;
    crc = modbus_crc16(tx_data, tx_length);
    tx_data[tx_length] = crc & 0xFF;
    tx_data[tx_length + 1] = (crc >> 8) & 0xFF;

    //HAL_UART_Transmit(slave->huart, tx_data, tx_length + 2, 100);
    CDC_print_blocking((char*) tx_data);
}

// 处理写单个寄存器 (功能码 0x06)
void handle_write_single_register(modbus_slave_t *slave, uint8_t *data) {
    uint16_t register_addr = (data[2] << 8) | data[3];
    uint16_t register_value = (data[4] << 8) | data[5];
    uint8_t tx_data[8];
    uint16_t crc;

    // 地址检查
    if (register_addr >= HOLDING_REGISTER_SIZE) {
        build_exception_response(slave, MODBUS_WRITE_SINGLE_REGISTER,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS);
        return;
    }

    // 写入寄存器
    slave->holding_register[register_addr] = register_value;

    // 响应与请求相同
    memcpy(tx_data, data, 6);
    crc = modbus_crc16(tx_data, 6);
    tx_data[6] = crc & 0xFF;
    tx_data[7] = (crc >> 8) & 0xFF;

    //HAL_UART_Transmit(slave->huart, tx_data, 8, 100);
    CDC_print_blocking((char*) tx_data);
}

// 处理写多个寄存器 (功能码 0x10)
void handle_write_multiple_registers(modbus_slave_t *slave, uint8_t *data) {
    uint16_t starting_addr = (data[2] << 8) | data[3];
    uint16_t quantity = (data[4] << 8) | data[5];
    uint8_t byte_count = data[6];
    uint8_t tx_data[12];
    uint16_t crc;

    // 地址和数量检查
    if (starting_addr + quantity > HOLDING_REGISTER_SIZE) {
        build_exception_response(slave, MODBUS_WRITE_MULTIPLE_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS);
        return;
    }

    if (quantity < 1 || quantity > 123 || byte_count != quantity * 2) {
        build_exception_response(slave, MODBUS_WRITE_MULTIPLE_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_VALUE);
        return;
    }

    // 写入寄存器
    for (uint16_t i = 0; i < quantity; i++) {
        slave->holding_register[starting_addr + i] = (data[7 + i * 2] << 8)
                | data[8 + i * 2];
    }

    // 构建响应
    tx_data[0] = MODBUS_SLAVE_ADDRESS;
    tx_data[1] = MODBUS_WRITE_MULTIPLE_REGISTERS;
    tx_data[2] = data[2];  // 起始地址高字节
    tx_data[3] = data[3];  // 起始地址低字节
    tx_data[4] = data[4];  // 数量高字节
    tx_data[5] = data[5];  // 数量低字节

    crc = modbus_crc16(tx_data, 6);
    tx_data[6] = crc & 0xFF;
    tx_data[7] = (crc >> 8) & 0xFF;

    //HAL_UART_Transmit(slave->huart, tx_data, 8, 100);
    CDC_print_blocking((char*) tx_data);
}

// 处理读输入寄存器 (功能码 0x04)
void handle_read_input_registers(modbus_slave_t *slave, uint8_t *data) {
    uint16_t starting_addr = (data[2] << 8) | data[3];
    uint16_t quantity = (data[4] << 8) | data[5];
    uint8_t tx_data[256];
    uint16_t crc;
    uint8_t tx_length;

    // 地址和数量检查
    if (starting_addr + quantity > INPUT_REGISTER_SIZE) {
        build_exception_response(slave, MODBUS_READ_INPUT_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS);
        return;
    }

    if (quantity < 1 || quantity > 125) {
        build_exception_response(slave, MODBUS_READ_INPUT_REGISTERS,
                                 MODBUS_EXCEPTION_ILLEGAL_DATA_VALUE);
        return;
    }

    // 构建响应
    tx_data[0] = MODBUS_SLAVE_ADDRESS;
    tx_data[1] = MODBUS_READ_INPUT_REGISTERS;
    tx_data[2] = quantity * 2;  // 字节数

    for (uint16_t i = 0; i < quantity; i++) {
        tx_data[3 + i * 2] = (slave->input_register[starting_addr + i] >> 8)
                             & 0xFF;
        tx_data[4 + i * 2] = slave->input_register[starting_addr + i] & 0xFF;
    }

    tx_length = 3 + quantity * 2;
    crc = modbus_crc16(tx_data, tx_length);
    tx_data[tx_length] = crc & 0xFF;
    tx_data[tx_length + 1] = (crc >> 8) & 0xFF;

    //HAL_UART_Transmit(slave->huart, tx_data, tx_length + 2, 100);
    CDC_print_blocking((char*) tx_data);
}
// 从Modbus寄存器数据解包字符串
// 输入: 寄存器数据缓冲区（每个寄存器2字节）
// 输出: 目标字符串缓冲区（需预先分配足够空间）
// 返回: 实际解包的字符数
int32_t UnpackStringFromModbus(uint8_t *reg_data, uint16_t reg_count,
                               char *out_str) {
    int32_t str_len = 0;

    for (uint16_t i = 0; i < reg_count; i++) {
        // 每个寄存器包含2个字符（高字节在前）
        char ch1 = (char) (reg_data[i * 2]);     // 第一个字符
        char ch2 = (char) (reg_data[i * 2 + 1]); // 第二个字符

        // 添加第一个字符（始终存在）
        out_str[str_len++] = ch1;

        // 第二个字符如果不是填充符#0，也添加
        if (ch2 != '\0') {
            out_str[str_len++] = ch2;
        } else {
            // 遇到填充符说明是奇数长度，字符串结束
            break;
        }
    }

    // 添加字符串结束符
    out_str[str_len] = '\0';

    return str_len;
}

extern void exec_line(char *line_buffer);

// 主循环调用-处理Modbus字符串接收（仿照USB_Process_RxData结构）
SD_TestResult_t Process_ModbusStringCommand(modbus_slave_t *slave) {
    uint8_t *rx_buf = slave->rx_buffer;
    uint16_t rx_len = slave->rx_index;

    // 最小帧长度检查: 从机地址(1字节) + 功能码(1) + 起始地址(2字节) + 寄存器数(2字节) + 字节数(1) + CRC(2) = 9
    if (rx_len < 9) {
        return SD_ELSE; // 帧太短，忽略
    }

    uint16_t starting_addr = (rx_buf[2] << 8) | rx_buf[3];    //起始地址

    // 提取寄存器数量
    uint16_t reg_count = (rx_buf[4] << 8) | rx_buf[5];

    // 提取字节数
    uint8_t byte_count = rx_buf[6];

    // 验证数据完整性
    if (byte_count != reg_count * 2 || rx_len < 7 + byte_count + 2) {
        return SD_ELSE; // 数据长度不匹配
    }

    // 定位寄存器数据起始位置（在字节数字段之后）
    uint8_t *reg_data = &rx_buf[7];

    // 分配输出缓冲区（最大可能字符串长度：reg_count * 2 + 1）
    char extracted_str[reg_count * 2 + 1];

    // 解包字符串
    int32_t actual_len = UnpackStringFromModbus(reg_data, reg_count,
                         extracted_str);

    // 在这里处理提取出的字符串
    if (actual_len > 0) {
        char test[BUFFER_SIZE + 2];
        sprintf(test, "%s\r\n", extracted_str);    //转换字符串并且加上尾缀

        switch (rx_buf[1]) {
        case MODBUS_GCode:;    //执行上位机传输的g代码
            //exec_line(test);    //---执行一行g代码

            //传给GRBL的串口//这里的g代码可能含实时指令，所以需要传给GRBL的串口
            char* p = test;
            while (*p) {
                HandleUartIT((uint8_t)*p++);
            }
            break;

        case MODBUS_SystemCommand:    	//执行上位机传输的系统指令
            lcd_hwy((uint8_t*) test, strlen(test));
            break;

        case MODBUS_WRITE_GCode2SD:    	//接受上位机的g代码文件
            if (starting_addr == 0) {
                //传输的是文件名
                char filename[actual_len + 3];
                sprintf(filename, "0:/%s", extracted_str);

                f_close(&SDFile);    	//关闭文件指针
                FRESULT fr = f_open(&SDFile, filename,FA_OPEN_APPEND | FA_WRITE); //注意文件名必须带盘符tuzi.gcode
                if (fr != FR_OK) {
                    // 错误处理
                    printf("Failed to open file: %d\n", fr);
                    return SD_TEST_OPEN_FAIL;
                }
            } else if (starting_addr == 65535) {
                f_close(&SDFile);    	//关闭文件指针
            } else {
                //传输的是文件内容
                FRESULT fr = f_lseek(&SDFile, f_size(&SDFile));// 手动移动到文件末尾
                if (fr != FR_OK)
                {
                    printf("Error: File seek failed (%d)\r\n", fr);
                    return SD_TEST_WRITE_FAIL;
                }

                UINT bw;
                fr = f_write(&SDFile, test, strlen(test), &bw);
                if (fr != FR_OK || bw != strlen(test)) {
                    //f_close(&SDFile);
                    printf("Error: File write failed %s (%d)\r\n", test, fr);
                    return SD_TEST_WRITE_FAIL;
                }
            }
            break;

        case MODBUS_WRITE_LaserPower2SD:    	//执行上位机传输的系统指令
            lcd_hwy((uint8_t*) test, strlen(test));
            break;

        default:
            build_exception_response(slave, slave->rx_buffer[1],
                                     MODBUS_EXCEPTION_ILLEGAL_FUNCTION);
            break;
        }

        // 示例：打印到调试串口
        //printf("rec:%s (len: %ld)\r\n", extracted_str, actual_len);

        // 发送Modbus响应帧（可选，如果需要应答）
        //CDC_print_blocking(extracted_str);
    }
    //Send_ModbusResponse(rx_buf[0], rx_buf[1], &rx_buf[2], 4);
    return SD_ALL_OK;
}
// Modbus帧处理
void modbus_process(modbus_slave_t *slave) {
    uint16_t crc_calculated, crc_received;

    // 检查最小帧长度
    if (slave->rx_index < 4)
        return;

    // 检查设备地址
    if (slave->rx_buffer[0] != MODBUS_SLAVE_ADDRESS)
        return;

    // 验证CRC
    crc_calculated = modbus_crc16(slave->rx_buffer, slave->rx_index - 2);
    crc_received = (slave->rx_buffer[slave->rx_index - 1] << 8)
                   | slave->rx_buffer[slave->rx_index - 2];

    if (crc_calculated != crc_received)
        return;

    // 根据功能码处理请求
    switch (slave->rx_buffer[1]) {
    case MODBUS_READ_HOLDING_REGISTERS:
        handle_read_holding_registers(slave, slave->rx_buffer);
        break;

    case MODBUS_WRITE_SINGLE_REGISTER:
        handle_write_single_register(slave, slave->rx_buffer);
        break;

    case MODBUS_WRITE_MULTIPLE_REGISTERS:
        handle_write_multiple_registers(slave, slave->rx_buffer);
        break;

    case MODBUS_READ_INPUT_REGISTERS:
        handle_read_input_registers(slave, slave->rx_buffer);
        break;

    case MODBUS_WRITE_GCode2SD:    	//把上位机传输的g代码文件写入sd卡
    case MODBUS_WRITE_LaserPower2SD:    	//把上位机传输的雕刻用灰度文件写入sd卡
    case MODBUS_GCode:    	//执行上位机传输的g代码
    case MODBUS_SystemCommand:    	//执行上位机传输的系统指令

        Process_ModbusStringCommand(slave);

        break;

    default:
        build_exception_response(slave, slave->rx_buffer[1],
                                 MODBUS_EXCEPTION_ILLEGAL_FUNCTION);
        break;
    }
}

/*
 // UART接收回调
 void modbus_uart_rx_callback(modbus_slave_t *slave)
 {
 slave->last_rx_time = HAL_GetTick();
 slave->rx_index++;

 // 继续接收下一个字节
 if(slave->rx_index < sizeof(slave->rx_buffer)) {
 HAL_UART_Receive_IT(slave->huart, &slave->rx_buffer[slave->rx_index], 1);
 }
 }

 // 定时器处理 (用于检测帧结束)
 void modbus_timer_elapsed(modbus_slave_t *slave)
 {
 uint32_t current_time = HAL_GetTick();

 // 检查是否超时 (3.5字符时间)
 if(slave->rx_index > 0 && (current_time - slave->last_rx_time) >= MODBUS_TIMEOUT_MS) {
 // 处理接收到的帧
 modbus_process(slave);

 // 重置接收状态
 slave->rx_index = 0;
 HAL_UART_Receive_IT(slave->huart, &slave->rx_buffer[0], 1);
 }
 }
 */

// 主循环调用-处理函数
extern RxBuffer_t rx_buffers[2];
void USB_Process_RxData(modbus_slave_t *slave) {
    for (int i = 0; i < 2; i++) {
        if (rx_buffers[i].ready && !rx_buffers[i].processing) {
            rx_buffers[i].processing = true;  // 加锁

            memcpy(slave->rx_buffer, rx_buffers[i].data,
                   rx_buffers[i].count - 1);            //去掉末尾的/n
            slave->rx_index = rx_buffers[i].count - 1;

            rx_buffers[i].count = 0;
            rx_buffers[i].ready = false;
            rx_buffers[i].processing = false; // 解锁

            //调用modbus处理// 处理接收到的帧
            modbus_process(slave);

            // 重置接收状态
            slave->rx_index = 0; //modbus_slave.rx_index = 0;
        }
    }
}
