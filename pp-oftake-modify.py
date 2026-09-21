import configparser
import json
from datetime import datetime, timedelta

import ssl
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager
from enum import Enum
from requests import Session

import sys
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

# To dobimo iz plinovodov konfiguracijo odjemnega mesta. Mi bomo morali to spremeniti in poslati nazaj.
sample_payload =  {
      'IsActive': True,
      'OfftakePointCode': '1-pc',
      'CityGateCode': '2904003',
      'Status': 1,
      'LoadType': 4,
      'SupplierCode': '51X-PLMB----SI-M',
      'MeasurementDeviceMultiplier': 1.0,
      'YearlyOfftake': 299,
      'ValidFrom': '2026-01-01T00:00:00',
      'IsProtectedConsumer': False,
      'OfftakeKind': 11,
      'InterruptibleSupplyContract': False,
      'AlternativeEnergySource': False,
      'ProtectedUserConsumePart': 0.0,
      'CurrentOfftakePointStatus': 0,
      'Gs1': '383112410000004201',
      'Cdk': 2,
      'ConsumptionGroups': [
        {
          'GroupPart': 100.0,
          'SubGroup1': 0.0,
          'SubGroup2': 0.0,
          'SubGroup3': 0.0,
          'SubGroup4': 0.0,
          'SubGroup5': 0.0,
          'SubGroup6': 0.0,
          'ConsumptionGroup': 1
        }
      ]
    }

headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "User-Agent": "PostmanRuntime/7.44.1"
    }

class MainWindow(QMainWindow):
    def __init__(self, offtake_points):
        super().__init__()

        self.setWindowTitle("Offtake Point Configuration")
        self.setGeometry(100, 100, 1100, 700)
        self.offtake_points = offtake_points

        self.point_list = QListWidget()
        self.point_list.setMinimumWidth(280)
        self.point_list.currentItemChanged.connect(self.show_point)

        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.addWidget(QLabel("Offtake points"))
        list_layout.addWidget(self.point_list)

        self.selected_point_label = QLabel("Select an offtake point")
        self.selected_point_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.parameters_form = QFormLayout()
        self.parameters_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        parameters_widget = QWidget()
        parameters_widget.setLayout(self.parameters_form)

        parameters_scroll = QScrollArea()
        parameters_scroll.setWidgetResizable(True)
        parameters_scroll.setWidget(parameters_widget)

        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)
        details_layout.addWidget(self.selected_point_label)
        details_layout.addWidget(parameters_scroll)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_panel)
        splitter.addWidget(details_panel)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(splitter)
        self.setCentralWidget(container)

        for point in self.offtake_points:
            code = point.get("OfftakePointCode") or point.get("Name") or "Unknown"
            item = QListWidgetItem(str(code))
            item.setData(Qt.ItemDataRole.UserRole, point)
            self.point_list.addItem(item)

        if self.point_list.count():
            self.point_list.setCurrentRow(0)
        else:
            self.selected_point_label.setText("No offtake points found")

    def show_point(self, current, previous):
        del previous
        if current is None:
            return

        point = current.data(Qt.ItemDataRole.UserRole)
        code = point.get("OfftakePointCode") or point.get("Name") or "Unknown"
        self.selected_point_label.setText(f"Parameters: {code}")

        while self.parameters_form.rowCount():
            self.parameters_form.removeRow(0)

        for parameter, value in point.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2, ensure_ascii=False)
            elif value is None:
                value = ""
            else:
                value = str(value)

            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setWordWrap(True)
            self.parameters_form.addRow(QLabel(str(parameter)), value_label)

class AllocationQuerryOptions(Enum):
    DAILY = "IncludeDailyMeasured"
    NOT_DAILY = "IncludeNotDailyMeasured"
    NOT_DAILY_FOR = "IncludeNotDailyMeasuredForecastsOnly"

class CityGate(Enum):
    ZIR = "2904003"
    ELB = "2905004"
    
class UnsafeTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")

        self.poolmanager = PoolManager(
            *args,
            ssl_context=ctx,
            **kwargs
        )

class PPSession(Session):
    def __init__(self, url, cert_path):
        super().__init__()
        self.url = url
        self.cert_path = cert_path

        self.mount('https://', UnsafeTLSAdapter())

    def read_allocation(self, option: AllocationQuerryOptions, citygate: CityGate):
        selected_date = datetime.now().date()-timedelta(days=25)
        date_str = selected_date.strftime("%Y-%m-%d")
        payload = {
            "query": {
                "periodStart": f"{date_str}",
                "options": f"{option.value}",
            }
        }

        response = self.post(self.url, json=payload, headers=headers, cert=self.cert_path)
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
        allocations = response.json().get("Allocations", [])
        return [
            allocation
            for allocation in allocations
            if allocation.get("CityGateCode") == citygate.value
        ]

    def read_configuration(self, citygate: CityGate = CityGate.ZIR):
        payload = {
            "all": True,
        }

        response = self.post(self.url, json=payload, headers=headers, cert=self.cert_path)
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
        offTakePoints = response.json().get("OffTakePoints", [])
        return response.json()
        # return [
        #     allocation
        #     for allocation in offTakePoints
        #     if allocation.get("CityGateCode") == citygate.value
        # ]

    def add_configuration(self, payload):
        payload = {"OffTakePoints": [payload]}
        response = self.post(self.url, json=payload, headers=headers, cert=self.cert_path)
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
        return response.json()

         


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('param.ini')

    okolje = config['API']['okolje']
    if okolje == 'TEST':
        baseUrl = config['API']['baseUrlTest']
    else:
        baseUrl = config['API']['baseUrl']

    cert_path = (
            config['CERT']['cert_file'],
            config['CERT']['key_file']
        )

    # session = PPSession(f'{baseUrl}/v1/PpWs/GetOfftakePointsAllocations', cert_path)
    # res = session.read(AllocationQuerryOptions.NOT_DAILY_FOR, CityGate.ELB)
    # session.close()

    session = PPSession(f'{baseUrl}/v1/PpWs/GetOfftakePointsConfigurationEis', cert_path)
    res = session.read_configuration()
    session.close()

    res = res.get("OfftakePoints", [])
    # for payload in res:
    #     point = OfftakePoint.from_payload_dict(payload)
    #     print(f"Adding OfftakePoint: {point.offtake_point_code} - {point.name}")
    #     session.add(point)
    #     session.commit()
    # session.close()

    # session = PPSession(f'{baseUrl}/v1/PpWs/AddOfftakePointsEis', cert_path)
    # res = session.add_configuration(sample_payload)
    # session.close()
    # print(res)

    app = QApplication(sys.argv)
    window = MainWindow(res)
    window.show()
    sys.exit(app.exec())
