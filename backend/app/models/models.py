"""
Database models for the Hotel Management System
"""
from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import enum


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps"""
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SoftDeleteMixin:
    """Mixin to add soft delete functionality"""
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    
    def soft_delete(self):
        """Mark record as deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        db.session.commit()


# Enums
class UserRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    CORPORATE_MANAGER = "corporate_manager"
    HOTEL_MANAGER = "hotel_manager"
    FRONT_DESK = "front_desk"
    HOUSEKEEPING = "housekeeping"
    MAINTENANCE = "maintenance"
    RESTAURANT_STAFF = "restaurant_staff"
    ACCOUNTANT = "accountant"


class RoomStatus(enum.Enum):
    OCCUPIED = "occupied"
    VACANT_DIRTY = "vacant_dirty"
    CLEAN_READY = "clean_ready"
    OUT_OF_ORDER = "out_of_order"
    INSPECTED = "inspected"


class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(enum.Enum):
    MPESA = "mpesa"
    STRIPE = "stripe"
    CASH = "cash"
    CARD = "card"


# Models
class Hotel(db.Model, TimestampMixin, SoftDeleteMixin):
    """Hotel/Property entity"""
    __tablename__ = 'hotels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    
    # Configuration
    check_in_time = db.Column(db.Time, default=datetime.strptime('15:00', '%H:%M').time())
    check_out_time = db.Column(db.Time, default=datetime.strptime('11:00', '%H:%M').time())
    currency = db.Column(db.String(3), default='USD')  # ISO currency code
    
    # Amenities (stored as JSON)
    amenities = db.Column(db.JSON, default=list)  # ['wifi', 'pool', 'gym', 'spa', 'parking']
    
    # Images
    logo_url = db.Column(db.String(500))
    images = db.Column(db.JSON, default=list)  # List of image URLs
    
    # Relationships
    rooms = db.relationship('Room', backref='hotel', lazy='dynamic', cascade='all, delete-orphan')
    staff = db.relationship('User', backref='hotel', lazy='dynamic')
    bookings = db.relationship('Booking', backref='hotel', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'phone': self.phone,
            'email': self.email,
            'website': self.website,
            'check_in_time': self.check_in_time.strftime('%H:%M') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%H:%M') if self.check_out_time else None,
            'currency': self.currency,
            'amenities': self.amenities,
            'logo_url': self.logo_url,
            'images': self.images,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class RoomType(db.Model, TimestampMixin, SoftDeleteMixin):
    """Room Type entity"""
    __tablename__ = 'room_types'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Standard, Deluxe, Suite
    description = db.Column(db.Text)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    max_occupancy = db.Column(db.Integer, default=2, nullable=False)
    bed_type = db.Column(db.String(50))  # King, Queen, Twin
    size_sqm = db.Column(db.Integer)
    
    # Amenities specific to room type
    amenities = db.Column(db.JSON, default=list)  # ['wifi', 'tv', 'minibar', 'balcony']
    images = db.Column(db.JSON, default=list)
    
    # Relationships
    hotel = db.relationship('Hotel', backref='room_types')
    rooms = db.relationship('Room', backref='room_type', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'hotel_id': self.hotel_id,
            'name': self.name,
            'description': self.description,
            'base_price': float(self.base_price),
            'max_occupancy': self.max_occupancy,
            'bed_type': self.bed_type,
            'size_sqm': self.size_sqm,
            'amenities': self.amenities,
            'images': self.images
        }


class Room(db.Model, TimestampMixin, SoftDeleteMixin):
    """Individual Room entity"""
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_type_id = db.Column(db.Integer, db.ForeignKey('room_types.id'), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    floor = db.Column(db.Integer)
    status = db.Column(db.Enum(RoomStatus), default=RoomStatus.CLEAN_READY, nullable=False)
    
    # Special attributes
    view_type = db.Column(db.String(50))  # Ocean, City, Garden
    is_accessible = db.Column(db.Boolean, default=False)
    is_smoking = db.Column(db.Boolean, default=False)
    
    # Relationships
    bookings = db.relationship('Booking', backref='room', lazy='dynamic')
    housekeeping_tasks = db.relationship('HousekeepingTask', backref='room', lazy='dynamic')
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('hotel_id', 'room_number', name='unique_room_number_per_hotel'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'hotel_id': self.hotel_id,
            'room_type_id': self.room_type_id,
            'room_number': self.room_number,
            'floor': self.floor,
            'status': self.status.value,
            'view_type': self.view_type,
            'is_accessible': self.is_accessible,
            'is_smoking': self.is_smoking,
            'room_type': self.room_type.to_dict() if self.room_type else None
        }


class User(db.Model, TimestampMixin, SoftDeleteMixin):
    """User entity (staff and guests)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    
    # Personal info
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    id_number = db.Column(db.String(50))  # ID/Passport number (text only)
    
    # Role and permissions
    role = db.Column(db.Enum(UserRole), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=True)
    
    # Additional properties
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    bookings = db.relationship('Booking', foreign_keys='Booking.guest_id', backref='guest', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role.value if self.role else None,
            'hotel_id': self.hotel_id,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
