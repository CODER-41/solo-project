"""
Booking and Payment models
"""
from datetime import datetime
from app import db
from .models import TimestampMixin, SoftDeleteMixin, BookingStatus, PaymentStatus, PaymentMethod
from decimal import Decimal


class Booking(db.Model, TimestampMixin, SoftDeleteMixin):
    """Booking entity"""
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # References
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=True)  # Assigned at check-in
    room_type_id = db.Column(db.Integer, db.ForeignKey('room_types.id'), nullable=False)
    
    # Dates
    check_in_date = db.Column(db.Date, nullable=False, index=True)
    check_out_date = db.Column(db.Date, nullable=False, index=True)
    actual_check_in = db.Column(db.DateTime)
    actual_check_out = db.Column(db.DateTime)
    
    # Guest details
    num_guests = db.Column(db.Integer, default=1, nullable=False)
    special_requests = db.Column(db.Text)
    
    # Pricing
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    
    # Status
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False, index=True)
    
    # Cancellation
    cancellation_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    refund_amount = db.Column(db.Numeric(10, 2))
    
    # Relationships
    payments = db.relationship('Payment', backref='booking', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Booking, self).__init__(**kwargs)
        if not self.booking_number:
            self.booking_number = self.generate_booking_number()
    
    @staticmethod
    def generate_booking_number():
        """Generate unique booking number"""
        import random
        import string
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"BK{timestamp}{random_str}"
    
    @property
    def num_nights(self):
        """Calculate number of nights"""
        return (self.check_out_date - self.check_in_date).days
    
    @property
    def is_active(self):
        """Check if booking is active"""
        return self.status in [BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN]
    
    def calculate_cancellation_charge(self):
        """Calculate cancellation charge based on policy"""
        from datetime import timedelta
        
        if not self.check_in_date:
            return Decimal('0.00')
        
        days_until_checkin = (self.check_in_date - datetime.utcnow().date()).days
        
        if days_until_checkin >= 2:  # 48 hours or more
            return Decimal('0.00')
        elif days_until_checkin >= 0:  # Within 48 hours
            return self.total_amount * Decimal('0.5')  # 50% charge
        else:  # No show
            return self.total_amount  # 100% charge
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_number': self.booking_number,
            'hotel_id': self.hotel_id,
            'guest_id': self.guest_id,
            'room_id': self.room_id,
            'room_type_id': self.room_type_id,
            'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
            'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
            'actual_check_in': self.actual_check_in.isoformat() if self.actual_check_in else None,
            'actual_check_out': self.actual_check_out.isoformat() if self.actual_check_out else None,
            'num_guests': self.num_guests,
            'num_nights': self.num_nights,
            'special_requests': self.special_requests,
            'total_amount': float(self.total_amount),
            'currency': self.currency,
            'status': self.status.value,
            'is_active': self.is_active,
            'guest': self.guest.to_dict() if self.guest else None,
            'room': self.room.to_dict() if self.room else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Payment(db.Model, TimestampMixin):
    """Payment entity"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    
    # Payment details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='USD')
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Transaction details
    transaction_id = db.Column(db.String(200), unique=True, index=True)
    payment_intent_id = db.Column(db.String(200))  # Stripe payment intent
    mpesa_receipt = db.Column(db.String(200))  # M-Pesa receipt number
    
    # Additional info
    description = db.Column(db.String(500))
    metadata = db.Column(db.JSON)  # Additional payment metadata
    
    # Refund info
    refunded_amount = db.Column(db.Numeric(10, 2), default=0)
    refund_reason = db.Column(db.Text)
    refunded_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'amount': float(self.amount),
            'currency': self.currency,
            'payment_method': self.payment_method.value,
            'status': self.status.value,
            'transaction_id': self.transaction_id,
            'description': self.description,
            'refunded_amount': float(self.refunded_amount) if self.refunded_amount else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class HousekeepingTask(db.Model, TimestampMixin):
    """Housekeeping task entity"""
    __tablename__ = 'housekeeping_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Task details
    task_type = db.Column(db.String(50), default='cleaning')  # cleaning, inspection, maintenance
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    status = db.Column(db.String(50), default='pending')  # pending, in_progress, completed, inspected
    
    # Timing
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    
    # Notes
    notes = db.Column(db.Text)
    issues_reported = db.Column(db.Text)
    
    # Inspector
    inspected_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    inspected_at = db.Column(db.DateTime)
    inspection_notes = db.Column(db.Text)
    
    # Relationships
    housekeeper = db.relationship('User', foreign_keys=[assigned_to], backref='housekeeping_tasks')
    inspector = db.relationship('User', foreign_keys=[inspected_by], backref='inspections')
    
    @property
    def duration_minutes(self):
        """Calculate task duration in minutes"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'assigned_to': self.assigned_to,
            'task_type': self.task_type,
            'priority': self.priority,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'notes': self.notes,
            'issues_reported': self.issues_reported,
            'room': self.room.to_dict() if self.room else None,
            'housekeeper': self.housekeeper.to_dict() if self.housekeeper else None
        }


class AuditLog(db.Model):
    """Audit log for tracking all system actions"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, login, logout
    entity_type = db.Column(db.String(50), nullable=False)  # booking, payment, room, user
    entity_id = db.Column(db.Integer)
    changes = db.Column(db.JSON)  # JSON of what changed
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = db.relationship('User', backref='audit_logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'changes': self.changes,
            'timestamp': self.timestamp.isoformat()
        }
