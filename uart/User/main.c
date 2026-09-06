#include "stm32f10x.h"                  // Device header
#include "Delay.h"
#include "Buzzer.h"
#include "OLED.h"
#include "CountSensor.h"
#include "Timer.h"
#include "Serial.h"
uint16_t num=0;
int main(void){
	OLED_Init();
	Timer_Init();
	CountSensor_Init();
	Serial_Init();
	OLED_ShowString(1,3,"Helloworld!");
	
	while(1){
		OLED_ShowNum(2,3,num,5);
	}
}
