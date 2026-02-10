// modbus.h
#ifndef __MODBUS_H
#define __MODBUS_H

#include "main.h"

// Modbus功能码
#define MODBUS_READ_COILS                0x01
#define MODBUS_READ_DISCRETE_INPUTS      0x02
#define MODBUS_READ_HOLDING_REGISTERS    0x03
#define MODBUS_READ_INPUT_REGISTERS      0x04
#define MODBUS_WRITE_SINGLE_COIL         0x05
#define MODBUS_WRITE_SINGLE_REGISTER     0x06
#define MODBUS_WRITE_MULTIPLE_COILS      0x0F
#define MODBUS_WRITE_MULTIPLE_REGISTERS  0x10

#define MODBUS_WRITE_GCode2SD            0x21
#define MODBUS_WRITE_LaserPower2SD       0x22

#define MODBUS_GCode            	     0x23
#define MODBUS_SystemCommand             0x24

#define MODBUS_test             		 0xFF

// Modbus异常码
#define MODBUS_EXCEPTION_ILLEGAL_FUNCTION        0x01
#define MODBUS_EXCEPTION_ILLEGAL_DATA_ADDRESS    0x02
#define MODBUS_EXCEPTION_ILLEGAL_DATA_VALUE      0x03

// 设备地址
#define MODBUS_SLAVE_ADDRESS     0x01

// 数据区大小
#define COIL_SIZE                100
#define DISCRETE_INPUT_SIZE      100
#define HOLDING_REGISTER_SIZE    100
#define INPUT_REGISTER_SIZE      100

// Modbus帧结构
typedef struct {
    uint8_t  address;
    uint8_t  function;
    uint16_t starting_address;
    uint16_t quantity;
    uint16_t byte_count;
    uint8_t  data[256];
    uint16_t crc;
} modbus_frame_t;

// Modbus从站结构
typedef struct {
    uint8_t  coil[COIL_SIZE];
    uint8_t  discrete_input[DISCRETE_INPUT_SIZE];
    uint16_t holding_register[HOLDING_REGISTER_SIZE];
    uint16_t input_register[INPUT_REGISTER_SIZE];

    uint8_t  rx_buffer[256];
    uint8_t  tx_buffer[256];
    uint16_t rx_index;
    uint32_t last_rx_time;

    //UART_HandleTypeDef *huart;
} modbus_slave_t;

// 函数声明
//void modbus_init(modbus_slave_t *slave, UART_HandleTypeDef *huart);
void modbus_init(modbus_slave_t *slave);
void modbus_process(modbus_slave_t *slave);
void modbus_timer_elapsed(modbus_slave_t *slave);
void modbus_uart_rx_callback(modbus_slave_t *slave);

// CRC计算函数
uint16_t modbus_crc16(uint8_t *data, uint16_t length);

void USB_Process_RxData(modbus_slave_t *slave);

#endif
