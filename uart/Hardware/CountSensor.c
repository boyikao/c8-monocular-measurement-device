#include "stm32f10x.h"                  // Device header
uint16_t CountSensor_count=1;
void CountSensor_Init(void)
{
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB,ENABLE);
	RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO,ENABLE);
	
	GPIO_InitTypeDef GPIO_InitStructure;
	GPIO_InitStructure.GPIO_Mode=GPIO_Mode_IPU;
	GPIO_InitStructure.GPIO_Pin=GPIO_Pin_14;
	GPIO_InitStructure.GPIO_Speed=GPIO_Speed_50MHz;
	GPIO_Init(GPIOB,&GPIO_InitStructure);
	
	GPIO_EXTILineConfig(GPIO_PortSourceGPIOB,GPIO_PinSource14);
	
	EXTI_InitTypeDef EXTI_InitStructure;
	EXTI_InitStructure.EXTI_Line=EXTI_Line14;
	EXTI_InitStructure.EXTI_LineCmd = ENABLE;
	EXTI_InitStructure.EXTI_Mode=EXTI_Mode_Interrupt;
	EXTI_InitStructure.EXTI_Trigger=EXTI_Trigger_Falling;
	EXTI_Init(&EXTI_InitStructure);
	
	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
	
	NVIC_InitTypeDef NVIC_InitStructure;
	NVIC_InitStructure.NVIC_IRQChannel=EXTI15_10_IRQn;
	NVIC_InitStructure.NVIC_IRQChannelCmd=ENABLE;
	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority=1;
	NVIC_InitStructure.NVIC_IRQChannelSubPriority=1;
	NVIC_Init(&NVIC_InitStructure);
}

uint16_t Get_Count(void){
	return CountSensor_count;
}

void EXTI15_10_IRQHandler(void){
	if(EXTI_GetITStatus(EXTI_Line14)==SET){
		
		if (GPIO_ReadInputDataBit(GPIOB, GPIO_Pin_14) == 0)
		{
			CountSensor_count ++;					//计数值自增一次
		}
//		CountSensor_count++;
		EXTI_ClearITPendingBit(EXTI_Line14);
	}
	
	
}


//void EXTI15_10_IRQHandler(void)
//{
//	if (EXTI_GetITStatus(EXTI_Line14) == SET)		//判断是否是外部中断14号线触发的中断
//	{
//		/*如果出现数据乱跳的现象，可再次判断引脚电平，以避免抖动*/
//		if (GPIO_ReadInputDataBit(GPIOB, GPIO_Pin_14) == 0)
//		{
//			CountSensor_count ++;					//计数值自增一次
//		}
//		EXTI_ClearITPendingBit(EXTI_Line14);		//清除外部中断14号线的中断标志位
//													//中断标志位必须清除
//													//否则中断将连续不断地触发，导致主程序卡死
//	}
//}

