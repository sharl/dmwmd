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
from win11toast import xml, notify
import darkdetect as dd

from config import Config
from getLog import getLog
from get_desktop_folders import get_desktop_folders
from utils import resource_path

TITLE = 'DMWMD'
# inspired from "Here's to Future Days"
TOOLTIP = "Don't mess with my desktop"

# default definitions
DEFAULT_SEARCH_PUBLIC = False
MONITOR_TARGETS = get_desktop_folders()
MONITOR_LIST = [1, 5, 10, 15, 30, 60]
DEFAULT_MONITOR_INTERVAL = MONITOR_LIST[-1]
DESTROY_LIST = [1, 5, 10, 15, 30, 60, 120]
DEFAULT_DESTROY_INTERVAL = DESTROY_LIST[-1]
LIFETIME_LIST = [0, 120, 360, 720, 1440]
DEFAULT_LIFETIME = LIFETIME_LIST[-1]

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
    search_public: bool
    # minutes
    monitor_interval: int
    # minutes
    destroy_interval: int
    # minutes
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
    return v


class TaskTray:
    def __init__(self):
        self.stop_monitor_event = threading.Event()
        self.stop_destroy_event = threading.Event()
        self.config = Config(TITLE)

        # 監視する対象: 発見した時刻
        self.monitor_files = dict()
        self.search_public = DEFAULT_SEARCH_PUBLIC
        self.monitor_interval = DEFAULT_MONITOR_INTERVAL
        self.destroy_interval = DEFAULT_DESTROY_INTERVAL
        self.lifetime = DEFAULT_LIFETIME
        self.delete_phisically = False

        image = Image.open(io.BytesIO(binascii.unhexlify(ICON.replace('\n', '').strip())))

        monitor_submenu = []
        for i in MONITOR_LIST:
            monitor_submenu.append(
                MenuItem(
                    f'{i} minute{"" if i == 1 else "s"}',
                    self.set_monitor_interval,
                    checked=lambda x: self.monitor_interval == int(str(x).split()[0]),
                ),
            )
        destroy_submenu = []
        for i in DESTROY_LIST:
            destroy_submenu.append(
                MenuItem(
                    f'{i} minute{"" if i == 1 else "s"}',
                    self.set_destroy_interval,
                    checked=lambda x: self.destroy_interval == int(str(x).split()[0]),
                ),
            )
        lifetime_submenu = []
        for i in LIFETIME_LIST:
            lifetime_submenu.append(
                MenuItem(
                    f'{int(i / 60)} hours' if i else 'immediately',
                    self.set_lifetime,
                    checked=lambda x: self.x_lifetime(x),
                ),
            )

        main_menu = Menu(
            MenuItem(f'{TOOLTIP} {getVersion()}', lambda: False, default=True),
            Menu.SEPARATOR,
            MenuItem('Enable Public Search', self.toggle_public, checked=lambda _: self.search_public),
            Menu.SEPARATOR,
            MenuItem('Monitor Interval', Menu(*monitor_submenu)),
            MenuItem('Destroy Interval', Menu(*destroy_submenu)),
            MenuItem('Notification Duration', Menu(*lifetime_submenu)),
            # 監視間隔・削除間隔のサブメニューとかゴミ箱行き設定のオンオフとかを入れる予定
            Menu.SEPARATOR,
            MenuItem('Exit', self.stopApp),
        )
        self.app = Icon(name=f'PYTHON.win32.{TITLE}', title=TOOLTIP, icon=image, menu=main_menu)
        # ここで設定読み込みして反映
        self.load_config()

    def load_config(self):
        try:
            setting = Setting(**self.config.load())
            self.monitor_interval = setting.monitor_interval
            self.destroy_interval = setting.destroy_interval
            self.lifetime = setting.lifetime
            self.delete_phisically = setting.delete_phisically
        except Exception:
            pass

    def save_config(self):
        setting = Setting(
            monitor_interval=self.monitor_interval,
            destroy_interval=self.destroy_interval,
            lifetime=self.lifetime,
            delete_phisically=self.delete_phisically,
        )
        self.config.save(asdict(setting))

    def _restart_monitor(self):
        # force restart monitor thread
        self.stop_monitor_event.set()
        time.sleep(1)
        self.stop_monitor_event.clear()
        threading.Thread(target=self.doMonitor).start()

    def _restart_destroy(self):
        # force restart destroy thread
        self.stop_destroy_event.set()
        time.sleep(1)
        self.stop_destroy_event.clear()
        threading.Thread(target=self.doDestroy).start()

    def toggle_public(self):
        self.search_public = not self.search_public
        logger.debug(f'set search public to {self.search_public}')

        self._restart_monitor()

    def set_monitor_interval(self, _, item: MenuItem):
        self.monitor_interval = int(str(item).split()[0])
        logger.debug(f'set monitor inverval to {self.monitor_interval}')

        self._restart_monitor()

    def set_destroy_interval(self, _, item: MenuItem):
        self.destroy_interval = int(str(item).split()[0])
        logger.debug(f'set destroy inverval to {self.destroy_interval}')

        self._restart_destroy()

    def _get_lifetime(self, item: MenuItem) -> int:
        ls = str(item).split()
        if len(ls) == 1:
            lifetime = 0
        else:
            # unit: hour -> minute
            lifetime = int(ls[0]) * 60
        return lifetime

    def x_lifetime(self, item: MenuItem) -> bool:
        return self.lifetime == self._get_lifetime(item)

    def set_lifetime(self, _, item: MenuItem):
        self.lifetime = self._get_lifetime(item)
        logger.debug(f'set lifetime to {self.lifetime}')

        # force restart destroy thread
        self.stop_destroy_event.set()
        time.sleep(1)
        self.stop_destroy_event.clear()
        threading.Thread(target=self.doDestroy).start()

    def doMonitor(self):
        monitor_targets = get_desktop_folders(self.search_public)

        while not self.stop_monitor_event.is_set():
            begin = time.time()

            for target_dir in monitor_targets:
                if not os.path.exists(target_dir):
                    continue

                for filename in os.listdir(target_dir):
                    if filename.lower() == 'desktop.ini':
                        continue

                    filepath = os.path.join(target_dir, filename)
                    if filepath not in self.monitor_files:
                        self.monitor_files[filepath] = time.time()

            elapsed = time.time() - begin
            sleep_time = max(0, self.monitor_interval * 60 - elapsed)
            if self.stop_monitor_event.wait(sleep_time):
                break

    def doDestroy(self):
        # Notification Specification
        # https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.toastnotification.tag?view=winrt-26100
        # tag max length: 64
        # group max length: 64
        def get_tag(filename: str) -> str:
            return os.path.basename(filename)[:64]

        def get_group(name: str) -> str:
            return name[:64]

        while not self.stop_destroy_event.is_set():
            begin = time.time()

            for filepath in self.monitor_files:
                if filepath.lower().endswith(('.lnk', '.url')):
                    # ショートカット（.lnk / .url）は発見次第、即座に一律排除
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                            logger.info(f'[DESTROY IMMEDIATE] {filepath}')
                    except Exception as e:
                        logger.warning(f'{e}: {filepath}')
                    continue

                # 通常のファイル・フォルダの滞在時間を計算
                elapsed_time = time.time() - self.monitor_files[filepath]
                if elapsed_time >= 60 * self.lifetime:
                    # open folder if notification clicked
                    # dirty ad hoc hack!!
                    xfolderpath = os.path.dirname(filepath).replace('\\', '/')
                    open_folder_xml = xml.replace('launch="http:"', f'launch="file:///{xfolderpath}"')
                    group = 'ACTION REQUIRED'
                    notify(
                        title=group,
                        body=filepath,
                        icon={
                            'src': resource_path('Assets/sample.ico'),
                            'placement': 'appLogoOverride',
                        },
                        xml=open_folder_xml,
                        app_id=TITLE,
                        group=get_group(group),
                        tag=get_tag(filepath),
                        audio={'silent': 'true'},
                    )
                    logger.info(f'notification {group} {filepath}')

            # omit disappeared files from monitor_files
            for filepath in self.monitor_files.copy():
                if filepath in self.monitor_files:
                    if not os.path.exists(filepath):
                        del self.monitor_files[filepath]

            elapsed = time.time() - begin
            sleep_time = max(0, self.destroy_interval * 60 - elapsed)
            if self.stop_destroy_event.wait(sleep_time):
                break

    def stopApp(self):
        self.stop_monitor_event.set()
        self.stop_destroy_event.set()
        self.app.stop()

    def runApp(self):
        self.stop_monitor_event.clear()
        self.stop_destroy_event.clear()

        self._restart_monitor()
        self._restart_destroy()

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
