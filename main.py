# -*- coding:utf-8 -*-
import logging
from DormRobber import DormRobber
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
users = [
    {
        "name":"xxx",
        "cookie":"PHPSESSID=41u2tas91u6d9oa8obr6o9k5mt; AJSTAT_ok_times=1; ASPSESSIONIDQSTTQRAC=EBHNOPABPLLPJBFIMNGONJIN; AJSTAT_ok_pages=3",
        "price":"3000"
    },
]
robber = DormRobber(
    users=users,
    start_time="10:00:00",
    interval=5.0
)
robber.start()