#include "stm32f10x.h"                  // Device header
#include "Delay.h"
#include "OLED.h"
#include "Serial.h"
#include "Key.h"

uint8_t KeyNum=0;			

int main(void)
{
	Serial_Init();
	Key_Init();
	OLED_Init();

	
	while(1){
		if(Key_GetNum()){
			if(KeyNum==0){
				KeyNum=1;
			}
			else{
				KeyNum=0;
			}
		}
		if(KeyNum==1){
			OLED_ShowString(1,1,"actual_size");
			OLED_ShowString(2,1,"distance");
			OLED_ShowString(3,1,"px");
			
			OLED_ShowNum(1,14,Serial_RxPacket[2],1);
			OLED_ShowNum(1,15,Serial_RxPacket[1],1);
			OLED_ShowNum(1,16,Serial_RxPacket[0],1);
			
			OLED_ShowNum(2,14,Serial_RxPacket[5],1);
			OLED_ShowNum(2,15,Serial_RxPacket[4],1);
			OLED_ShowNum(2,16,Serial_RxPacket[3],1);
			
			OLED_ShowNum(3,14,Serial_RxPacket[8],1);
			OLED_ShowNum(3,15,Serial_RxPacket[7],1);
			OLED_ShowNum(3,16,Serial_RxPacket[6],1);
		}
		else{
			OLED_Clear();
		}
		
		
		
	}
}
