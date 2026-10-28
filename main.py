# -*- coding:utf-8 -*-
import logging
import ActivityManager

cook = "utpstr=1; ASPSESSIONIDQQRTRRDD=DPOLLBNDCOLAPDFGOEDEMHPN; PHPSESSID=0dae6usmdluevuv5raveri61dh; AJSTAT_ok_times=3; AJSTAT_ok_pages=32"

a = ActivityManager.ActivityManager()
a.set_login(cook)
ls = a.get_personal_activity_list(deep=True)
print(ls)