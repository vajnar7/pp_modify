import os
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
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from model import OfftakePoint, get_session

# Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'vajnar')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'AldebaraN7#')
DB_NAME = os.getenv('DB_NAME', 'pp_offtake')

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
    EDITABLE_PARAMETERS = (
        'Name',
        'IsActive',
        'OfftakePointCode',
        'CityGateCode',
        'Status',
        'LoadType',
        'SupplierCode',
        'MeasurementDeviceMultiplier',
        'YearlyOfftake',
        'ValidFrom',
        'IsProtectedConsumer',
        'OfftakeKind',
        'InterruptibleSupplyContract',
        'AlternativeEnergySource',
        'ProtectedUserConsumePart',
        'CurrentOfftakePointStatus',
        'Gs1',
        'Cdk',
        'ConsumptionGroups',
    )
    BOOLEAN_PARAMETERS = {
        'IsActive',
        'IsProtectedConsumer',
        'InterruptibleSupplyContract',
        'AlternativeEnergySource',
    }
    INTEGER_PARAMETERS = {
        'Status',
        'LoadType',
        'YearlyOfftake',
        'OfftakeKind',
        'CurrentOfftakePointStatus',
        'Cdk',
    }
    FLOAT_PARAMETERS = {
        'MeasurementDeviceMultiplier',
        'ProtectedUserConsumePart',
    }
    OPTIONAL_PARAMETERS = {
        'SupplierCode',
        'YearlyOfftake',
        'ValidFrom',
        'OfftakeKind',
        'MeasurementDeviceMultiplier',
        'ProtectedUserConsumePart',
        'CurrentOfftakePointStatus',
        'Gs1',
        'Cdk',
    }

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
        self.parameter_editors = {}
        parameters_widget = QWidget()
        parameters_widget.setLayout(self.parameters_form)

        parameters_scroll = QScrollArea()
        parameters_scroll.setWidgetResizable(True)
        parameters_scroll.setWidget(parameters_widget)

        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)
        details_layout.addWidget(self.selected_point_label)
        details_layout.addWidget(parameters_scroll)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.ok_button = QPushButton('OK')
        self.ok_button.clicked.connect(self.save_selected_point)
        button_layout.addWidget(self.ok_button)
        details_layout.addLayout(button_layout)

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
        self.parameter_editors.clear()

        for parameter in self.EDITABLE_PARAMETERS:
            value = point.get(parameter)
            if parameter == 'Name':
                value = point.get('Name') or point.get('OfftakePointCode') or 'Unknown'

            if parameter in self.BOOLEAN_PARAMETERS:
                editor = QCheckBox()
                editor.setChecked(bool(value))
            elif parameter == 'ConsumptionGroups':
                editor = QPlainTextEdit()
                editor.setPlainText(json.dumps(value or [], indent=2, ensure_ascii=False))
                editor.setMaximumHeight(150)
            else:
                editor = QLineEdit('' if value is None else str(value))

            self.parameter_editors[parameter] = editor
            self.parameters_form.addRow(QLabel(parameter), editor)

    def save_selected_point(self):
        current_item = self.point_list.currentItem()
        if current_item is None:
            return

        selected_point = current_item.data(Qt.ItemDataRole.UserRole)
        old_code = selected_point.get('OfftakePointCode')
        payload = {}
        try:
            for parameter, editor in self.parameter_editors.items():
                if parameter in self.BOOLEAN_PARAMETERS:
                    value = editor.isChecked()
                elif parameter == 'ConsumptionGroups':
                    raw_value = editor.toPlainText().strip()
                    value = json.loads(raw_value) if raw_value else []
                    if not isinstance(value, list):
                        raise ValueError('ConsumptionGroups must be a JSON list.')
                else:
                    raw_value = editor.text().strip()
                    if not raw_value and parameter in self.OPTIONAL_PARAMETERS:
                        value = None
                    elif parameter in self.INTEGER_PARAMETERS:
                        value = int(raw_value)
                    elif parameter in self.FLOAT_PARAMETERS:
                        value = float(raw_value)
                    elif parameter == 'ValidFrom':
                        value = datetime.fromisoformat(raw_value.replace('Z', '+00:00')).isoformat() if raw_value else None
                    else:
                        value = raw_value
                payload[parameter] = value

            if not payload['Name'] or not payload['OfftakePointCode'] or not payload['CityGateCode']:
                raise ValueError('Name, OfftakePointCode, and CityGateCode are required.')
        except (ValueError, json.JSONDecodeError) as error:
            QMessageBox.warning(self, 'Invalid parameters', str(error))
            return

        db_session = get_session(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        try:
            point = db_session.query(OfftakePoint).filter_by(offtake_point_code=old_code).one()
            point.update_from_payload(payload)
            db_session.commit()
        except Exception as error:
            db_session.rollback()
            QMessageBox.critical(self, 'Database update failed', str(error))
            return
        finally:
            db_session.close()

        selected_point.update(payload)
        current_item.setText(payload['OfftakePointCode'])
        QMessageBox.information(self, 'Saved', 'Offtake point updated in the database.')

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

    session = PPSession(f'{baseUrl}/v1/PpWs/GetOfftakePointsConfigurationEis', cert_path)
    res = session.read_configuration()
    session.close()

    res = res.get("OfftakePoints", [])
    res = [point for point in res if point.get("CityGateCode") in [CityGate.ZIR.value, CityGate.ELB.value]]
    if res:
        db_session = get_session(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        try:
            point_codes = [point['OfftakePointCode'] for point in res]
            existing_points = {
                point.offtake_point_code: point
                for point in db_session.query(OfftakePoint)
                .filter(OfftakePoint.offtake_point_code.in_(point_codes))
                .all()
            }

            for payload in res:
                point_code = payload['OfftakePointCode']
                point = existing_points.get(point_code)
                if point is None:
                    point = OfftakePoint.from_payload_dict(payload)
                    db_session.add(point)
                    existing_points[point_code] = point
                else:
                    point.update_from_payload(payload)

                payload.update(point.to_payload_dict())
                payload['Name'] = point.name

            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    # session = PPSession(f'{baseUrl}/v1/PpWs/AddOfftakePointsEis', cert_path)
    # res = session.add_configuration(sample_payload)
    # session.close()
    # print(res)

    app = QApplication(sys.argv)
    window = MainWindow(res)
    window.show()
    sys.exit(app.exec())
