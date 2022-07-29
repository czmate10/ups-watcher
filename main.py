import subprocess
from time import sleep
from typing import Dict

import dacite as dacite
import datadog
import yaml

from config_context import DatadogConfig, ConfigContext

TEST_OUTPUT = """
APC      : 001,027,0676
DATE     : 2022-07-29 10:09:40 +0100
HOSTNAME : raspberrypi
VERSION  : 3.14.14 (31 May 2016) debian
UPSNAME  : APC-Smart-UPS-1500
CABLE    : USB Cable
DRIVER   : USB UPS Driver
UPSMODE  : Stand Alone
STARTTIME: 2022-07-28 17:04:29 +0100
MODEL    : Smart-UPS_1500
STATUS   : ONLINE
BCHARGE  : 99.0 Percent
TIMELEFT : 157.2 Minutes
MBATTCHG : 5 Percent
MINTIMEL : 3 Minutes
MAXTIME  : 0 Seconds
ALARMDEL : 30 Seconds
BATTV    : 26.8 Volts
NUMXFERS : 0
TONBATT  : 0 Seconds
CUMONBATT: 0 Seconds
XOFFBATT : N/A
STATFLAG : 0x05000008
MANDATE  : 2022-03-04
SERIALNO : 0000
NOMBATTV : 24.0 Volts
FIRMWARE : UPS 04.6 / ID=1015
END APC  : 2022-07-29 10:09:40 +0100
"""


class UpsWatcher:
    def __init__(self, datadog_config: DatadogConfig):
        self.watchlist = datadog_config.watchlist
        datadog.initialize(statsd_host=datadog_config.host, statsd_port=datadog_config.port, statsd_namespace=datadog_config.namespace)

    def start(self):
        while True:
            result = subprocess.run(["apcaccess", "status"], capture_output=True).stdout
            values = self.apcaccess_output_to_dict(str(result, 'utf-8'))

            processed_values = self.process_values(values)
            self.send_to_datadog(processed_values)

            sleep(30)

    def send_to_datadog(self, metrics: Dict[str, str]):
        for metric_name, metric_value in metrics.items():
            if type(metric_value) not in (int, float):
                continue

            print(f'{metric_name} = {metric_value}')
            print(datadog.statsd.histogram(metric=metric_name, value=metric_value))

    def process_values(self, values: Dict[str, str]) -> Dict[str, str]:
        final_values = {}
        for key, value in values.items():
            if key not in self.watchlist:
                continue

            if value == 'N/A':
                continue
            elif key in ('BCHARGE', 'MBATTCHG'):  # 99.0 Percent
                final_value = float(value.split(' ')[0])
            elif key in ('BATTV', 'NOMBATTV'):  # 26.8 Volts
                final_value = float(value.split(' ')[0])
            elif key in ('TIMELEFT', 'MINTIMEL', 'MAXTIME', 'ALARMDEL', 'TONBATT', 'CUMONBATT'):  # 157.2 Minutes
                split = value.split(' ')
                if len(split) != 2:
                    continue

                if split[1] == 'Days':
                    final_value = float(split[0]) * 3600 * 24
                elif split[1] == 'Hours':
                    final_value = float(split[0]) * 3600
                elif split[1] == 'Minutes':
                    final_value = float(split[0]) * 60
                else:
                    final_value = float(split[0])
            else:
                final_value = value

            final_values[key] = final_value

        return final_values

    @staticmethod
    def apcaccess_output_to_dict(apcaccess_output: str) -> Dict[str, str]:
        result = {}
        for line in apcaccess_output.split('\n'):
            try:
                key, value = line.split(':')
            except ValueError:
                continue

            key, value = key.strip(), value.strip()
            result[key] = value

        return result


if __name__ == '__main__':
    with open('config.yaml', 'r') as file:
        config = dacite.from_dict(data_class=ConfigContext, data=yaml.load(file, Loader=yaml.Loader))

    ups_watcher = UpsWatcher(config.datadog_config)
    ups_watcher.start()
