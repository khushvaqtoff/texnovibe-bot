import re 
content = open('bot.py', encoding='utf-8').read() 
content = content.replace('get_workplace, get_product,', 'get_product,') 
content = content.replace('AGENT, WORK_PLACE, PAY_DAY, CONFIRM', 'AGENT, PAY_DAY, CONFIRM') 
open('bot.py', 'w', encoding='utf-8').write(content) 
