import json
from datetime import datetime
from functools import lru_cache
from urllib.parse import quote_plus

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
@lru_cache(maxsize=32)
def get_engine(host, user, password, database):
    """Return a cached SQLAlchemy engine for a given database configuration."""
    url = f'mysql+mysqlconnector://{quote_plus(user)}:{quote_plus(password)}@{host}/{database}'
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=5,
        max_overflow=10,
    )

@lru_cache(maxsize=32)
def get_session_factory(host, user, password, database):
    """Return a cached session factory using a shared engine for the database."""
    engine = get_engine(host, user, password, database)
    Base.metadata.create_all(engine)  # Ensure tables are created
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session(host, user, password, database):
    """Create a request-scoped database session from the shared factory."""
    return get_session_factory(host, user, password, database)()

class OfftakePoint(Base):
    __tablename__ = 'offtake_points'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default='Unknown')
    is_active = Column(Boolean, nullable=False, default=True)
    offtake_point_code = Column(String(100), nullable=False, unique=True)
    city_gate_code = Column(String(50), nullable=False)
    status = Column(Integer, nullable=False, default=1)
    load_type = Column(Integer, nullable=False, default=4)
    supplier_code = Column(String(100), nullable=True)
    measurement_device_multiplier = Column(Float, nullable=True, default=1.0)
    yearly_offtake = Column(Integer, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    is_protected_consumer = Column(Boolean, nullable=False, default=False)
    offtake_kind = Column(Integer, nullable=True)
    interruptible_supply_contract = Column(Boolean, nullable=False, default=False)
    alternative_energy_source = Column(Boolean, nullable=False, default=False)
    protected_user_consume_part = Column(Float, nullable=True, default=0.0)
    current_offtake_point_status = Column(Integer, nullable=True, default=0)
    gs1 = Column(String(255), nullable=True)
    cdk = Column(Integer, nullable=True)
    consumption_groups = Column(Text, nullable=True)

    @property
    def consumption_groups_data(self):
        if not self.consumption_groups:
            return []
        try:
            value = json.loads(self.consumption_groups)
            return value if isinstance(value, list) else []
        except (TypeError, ValueError):
            return []

    @consumption_groups_data.setter
    def consumption_groups_data(self, value):
        if value is None:
            self.consumption_groups = None
        else:
            self.consumption_groups = json.dumps(value, ensure_ascii=False)

    def to_payload_dict(self):
        return {
            'IsActive': self.is_active,
            'OfftakePointCode': self.offtake_point_code,
            'CityGateCode': self.city_gate_code,
            'Status': self.status,
            'LoadType': self.load_type,
            'SupplierCode': self.supplier_code,
            'MeasurementDeviceMultiplier': self.measurement_device_multiplier,
            'YearlyOfftake': self.yearly_offtake,
            'ValidFrom': self.valid_from.isoformat() if self.valid_from else None,
            'IsProtectedConsumer': self.is_protected_consumer,
            'OfftakeKind': self.offtake_kind,
            'InterruptibleSupplyContract': self.interruptible_supply_contract,
            'AlternativeEnergySource': self.alternative_energy_source,
            'ProtectedUserConsumePart': self.protected_user_consume_part,
            'CurrentOfftakePointStatus': self.current_offtake_point_status,
            'Gs1': self.gs1,
            'Cdk': self.cdk,
            'ConsumptionGroups': self.consumption_groups_data,
        }

    # syncing existing database rows
    # patching/refreshing previously saved records
    def update_from_payload(self, payload):
        valid_from = payload.get('ValidFrom')
        if isinstance(valid_from, str):
            try:
                valid_from = datetime.fromisoformat(valid_from.replace('Z', '+00:00'))
            except ValueError:
                valid_from = None

        self.name = payload.get('Name') or payload.get('OfftakePointCode') or self.name or 'Unknown'
        self.is_active = bool(payload.get('IsActive', self.is_active))
        self.offtake_point_code = payload.get('OfftakePointCode') or self.offtake_point_code
        self.city_gate_code = payload.get('CityGateCode') or self.city_gate_code
        self.status = payload.get('Status', self.status)
        self.load_type = payload.get('LoadType', self.load_type)
        self.supplier_code = payload.get('SupplierCode', self.supplier_code)
        self.measurement_device_multiplier = payload.get('MeasurementDeviceMultiplier', self.measurement_device_multiplier)
        self.yearly_offtake = payload.get('YearlyOfftake', self.yearly_offtake)
        self.valid_from = valid_from if valid_from is not None else self.valid_from
        self.is_protected_consumer = bool(payload.get('IsProtectedConsumer', self.is_protected_consumer))
        self.offtake_kind = payload.get('OfftakeKind', self.offtake_kind)
        self.interruptible_supply_contract = bool(payload.get('InterruptibleSupplyContract', self.interruptible_supply_contract))
        self.alternative_energy_source = bool(payload.get('AlternativeEnergySource', self.alternative_energy_source))
        self.protected_user_consume_part = payload.get('ProtectedUserConsumePart', self.protected_user_consume_part)
        self.current_offtake_point_status = payload.get('CurrentOfftakePointStatus', self.current_offtake_point_status)
        self.gs1 = payload.get('Gs1', self.gs1)
        self.cdk = payload.get('Cdk', self.cdk)
        if 'ConsumptionGroups' in payload:
            self.consumption_groups_data = payload.get('ConsumptionGroups', self.consumption_groups_data)
        return self

    # for new inserts
    # object creation from an API response payload
    @classmethod
    def from_payload_dict(cls, payload):
        instance = cls(
            name=payload.get('OfftakePointCode') or payload.get('Name') or 'Unknown',
            is_active=bool(payload.get('IsActive', True)),
            offtake_point_code=payload.get('OfftakePointCode'),
            city_gate_code=payload.get('CityGateCode'),
            status=payload.get('Status', 1),
            load_type=payload.get('LoadType', 4),
            supplier_code=payload.get('SupplierCode'),
            measurement_device_multiplier=payload.get('MeasurementDeviceMultiplier', 1.0),
            yearly_offtake=payload.get('YearlyOfftake'),
            valid_from=None,
            is_protected_consumer=bool(payload.get('IsProtectedConsumer', False)),
            offtake_kind=payload.get('OfftakeKind'),
            interruptible_supply_contract=bool(payload.get('InterruptibleSupplyContract', False)),
            alternative_energy_source=bool(payload.get('AlternativeEnergySource', False)),
            protected_user_consume_part=payload.get('ProtectedUserConsumePart', 0.0),
            current_offtake_point_status=payload.get('CurrentOfftakePointStatus', 0),
            gs1=payload.get('Gs1'),
            cdk=payload.get('Cdk'),
        )
        instance.update_from_payload(payload)
        return instance


# Example usage:
# payload = {
#     'IsActive': True,
#     'OfftakePointCode': '1-pc',
#     'CityGateCode': '2904003',
#     'Status': 1,
#     'LoadType': 4,
#     'SupplierCode': '51X-PLMB----SI-M',
#     'MeasurementDeviceMultiplier': 1.0,
#     'YearlyOfftake': 299,
#     'ValidFrom': '2026-01-01T00:00:00',
#     'IsProtectedConsumer': False,
#     'OfftakeKind': 11,
#     'InterruptibleSupplyContract': False,
#     'AlternativeEnergySource': False,
#     'ProtectedUserConsumePart': 0.0,
#     'CurrentOfftakePointStatus': 0,
#     'Gs1': '383112410000004201',
#     'Cdk': 2,
#     'ConsumptionGroups': [{
#         'GroupPart': 100.0,
#         'SubGroup1': 0.0,
#         'SubGroup2': 0.0,
#         'SubGroup3': 0.0,
#         'SubGroup4': 0.0,
#         'SubGroup5': 0.0,
#         'SubGroup6': 0.0,
#         'ConsumptionGroup': 1,
#     }],
# }
#
# point = OfftakePoint.from_payload_dict(payload)
# print(point.to_payload_dict())
#
# session = get_session(host, user, password, database)
# session.add(point)
# session.commit()