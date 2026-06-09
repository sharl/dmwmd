# -*- coding: utf-8 -*-
from dataclasses import asdict, dataclass
import binascii
import ctypes
import io
import logging
import logging.handlers
import os
import threading
import time

from PIL import Image
from pystray import Icon, Menu, MenuItem
from win11toast import notify
import darkdetect as dd
import schedule

from config import Config
from getLog import getLog
from get_desktop_folders import get_desktop_folders
from utils import resource_path

TITLE = 'DMWMD'
# inspired from "Here's to Future Days"
TOOLTIP = "Don't mess with my desktop"


# default definitions
WATCH_TARGETS = get_desktop_folders()
WATCH_INTERVAL = 60 * 5
LIFETIME = 60 * 30

# logger settings
logname = getLog(TITLE, 'log.log')
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # logging.handlers.RotatingFileHandler(logname, encoding='utf-8', maxBytes=1000000, backupCount=0),
        logging.StreamHandler(),
    ],
    datefmt='%Y/%m/%d %X'
)
logger = logging.getLogger(TITLE)
logger.setLevel(logging.DEBUG)


@dataclass
class Setting:
    # second
    watch_interval: int
    # second
    lifetime: int
    delete_phisically: bool


PreferredAppMode = {
    'Light': 0,
    'Dark': 1,
}
# https://github.com/moses-palmer/pystray/issues/130
ctypes.windll['uxtheme.dll'][135](PreferredAppMode[dd.theme()])


def getVersion():
    v = 'test'
    try:
        with open(resource_path('Assets/version.txt')) as fd:
            v = fd.read().strip().removeprefix('v')
    except Exception:
        pass
    return f'{TITLE} {v}'


class TaskTray:
    def __init__(self):
        self.stop_event = threading.Event()
        self.config = Config(TITLE)

        # 監視する対象: 発見した時刻
        self.watch_files = dict()
        self.watch_interval = WATCH_INTERVAL
        self.lifetime = LIFETIME
        self.delete_phisically = False

        image = Image.open(io.BytesIO(binascii.unhexlify(ICON.replace('\n', '').strip())))
        main_menu = Menu(
            # MenuItem('Manual Cleanup', self.on_menu_delete),
            # 監視間隔のサブメニューとかゴミ箱行き設定のオンオフとかを入れる予定
            Menu.SEPARATOR,
            MenuItem(f'Exit {getVersion()}', self.stopApp),
        )
        self.app = Icon(name=f'PYTHON.win32.{TITLE}', title=TOOLTIP, icon=image, menu=main_menu)
        # ここで設定読み込みして反映
        self.load_config()

    def load_config(self):
        try:
            setting = Setting(**self.config.load())
            self.watch_interval = setting.watch_interval
            self.lifetime = setting.lifetime
            self.delete_phisically = setting.delete_phisically
        except Exception:
            pass

    def save_config(self):
        setting = Setting(
            watch_interval=self.watch_interval,
            lifetime=self.lifetime,
            delete_phisically=self.delete_phisically,
        )
        self.config.save(asdict(setting))

    def doMonitor(self):
        for target_dir in WATCH_TARGETS:
            if not os.path.exists(target_dir):
                continue

            for filename in os.listdir(target_dir):
                if filename.lower() == 'desktop.ini':
                    continue

                filepath = os.path.join(target_dir, filename)
                if filepath not in self.watch_files:
                    # 初めて発見した時刻を記録
                    # もしくは st_ctime, st_mtime 的なやつ?
                    # 作られたばかりなら様子を見てやってもいい
                    # ディレクトリの扱いはまたあとで
                    logger.debug(f'found {filepath}')
                    self.watch_files[filepath] = time.time()

    def doRemove(self):
        for filepath in self.watch_files:
            # 1. ショートカット（.lnk / .url）は発見次第、即座に一律排除
            if filepath.lower().endswith((".lnk", ".url")):
                logger.info(f"[DESTROY IMMEDIATE] {filepath}")
                try:
                    # 即削除またはゴミ箱移動
                    # os.remove(filepath)
                    logger.info(f"[DESTROY Done] {filepath} (DEBUG: not deleted)")
                except Exception as e:
                    logger.warning(f'{e}: {filepath}')
                continue

                # 2. 通常のファイル・フォルダの滞在時間カウント
                # 滞在時間を計算
                elapsed_time = time.time() - self.watch_files[filepath]
                if elapsed_time > self.lifetime:
                    logger.debug(f"[WARNING / ACTION] {filepath} has expired ({int(elapsed_time)}s).")
                    notify(f'{filepath} expired (still not remove)')

        # omit disappeared files from watch_files
        for filepath in self.watch_files.copy():
            if filepath not in self.watch_files:
                del self.watch_files[filepath]

    def runSchedule(self):
        self.doMonitor()

        schedule.every(WATCH_INTERVAL).seconds.do(self.doMonitor)

        while not self.stop_event.is_set():
            schedule.run_pending()
            if self.stop_event.wait(1):
                break
        schedule.clear()

    def stopApp(self):
        self.stop_event.set()
        self.app.stop()

    def runApp(self):
        self.stop_event.clear()

        task_thread = threading.Thread(target=self.runSchedule)
        task_thread.start()

        self.app.run()


ICON = """
89504e470d0a1a0a0000000d4948445200000010000000100803000000282d0f53000000206348524d00007a26000080840000fa00000080e8000075
300000ea6000003a98000017709cba513c00000105504c5445378eca2c86c42b86c42786c4338eca2887c5378ec9368dc9338dc9438cc83b85c23a84
c2438cc72b87c4368ec92c87c4388fca2885c3538ac5e772abf26ea8e672ab548bc62986c42a85c32b85c3348ecad873acff6ca5fe6da6d872ac428c
c8388eca368fca4882c0e570aaff6ea7e571aa4882bf358eca2d8fcb4c8bc6f56fa84c8ac62a86c42c85c3418dc84f8bc6f46fa8f46ea84e8bc6428d
c92d85c3448cc8e371abf56ea8fe6ea7e371aa348fca458cc7f06fa8ff6da5348fcb2887c43984c2ef70a9ff6da6388ec9398eca3984c1f16fa82686
c4e471aa438bc7358fca4683c0418cc7418cc8e273acef6fa9448bc72886c42e87c4458bc7468cc72d86c4ffffff47455a0900000001624b4744560a
0de9890000000774494d4507ea0608142e35776489a8000000dc4944415418d345ceeb76c1401405e0939318a51adaba254287aa6a884b5b4c091d69
a554dd8af77f1533c1f26fafbdcef9d60650104051352d840450e6b0a8ae22d1eb987683613d0e0809bcbdbb4f2653e94c16409e18662467e5f356e1
c154c41b6096164b8fe5f253e599a2bc9146f5c5b66b554442844168dd69345bedd7b7f793e1689d6e8f31fba373328cfec01d32367407232730e827
1f7b8c7963ae7e05c6b73af165e1f31f7a34ccd85416d359ffbce377ee7a9e3bbfec50ff7ccbf21721074018ba2866cbd56ab9de18c18e3812fd9f6f
777caf8b0c07f9131c4674ba97560000000049454e44ae426082
"""

if __name__ == '__main__':
    TaskTray().runApp()
