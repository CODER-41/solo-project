"""
Booking routes
"""
from flask import Blueprint, request, jsonify
from app import db
from app.models.models import Hotel, Room, RoomType, RoomStatus
from app.models.booking import Booking, Payment, BookingStatus, PaymentStatus
from app.routes.auth import token_required
from datetime import datetime, date
from sqlalchemy import and_, or_

bp = Blueprint('bookings', __name__)


@bp.route('/search', methods=['POST'])
def search_availability():
    """Search for available rooms"""
    data = request.get_json()
    
    # Validate required fields
    required = ['hotel_id', 'check_in_date', 'check_out_date', 'num_guests']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    try:
        # Parse dates
        check_in = datetime.strptime(data['check_in_date'], '%Y-%m-%d').date()
        check_out = datetime.strptime(data['check_out_date'], '%Y-%m-%d').date()
        
        if check_in >= check_out:
            return jsonify({'error': 'Check-out must be after check-in'}), 400
        
        if check_in < date.today():
            return jsonify({'error': 'Check-in date cannot be in the past'}), 400
        
        hotel_id = data['hotel_id']
        num_guests = data['num_guests']
        
        # Get all room types for this hotel
        room_types = RoomType.query.filter_by(
            hotel_id=hotel_id,
            is_deleted=False
        ).filter(
            RoomType.max_occupancy >= num_guests
        ).all()
        
        available_types = []
        
        for room_type in room_types:
            # Count total rooms of this type
            total_rooms = Room.query.filter_by(
                hotel_id=hotel_id,
                room_type_id=room_type.id,
                is_deleted=False
            ).filter(
                Room.status != RoomStatus.OUT_OF_ORDER
            ).count()
            
            # Count booked rooms for this date range
            booked_rooms = db.session.query(Booking).filter(
                Booking.room_type_id == room_type.id,
                Booking.hotel_id == hotel_id,
                Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN]),
                or_(
                    and_(
                        Booking.check_in_date <= check_in,
                        Booking.check_out_date > check_in
                    ),
                    and_(
                        Booking.check_in_date < check_out,
                        Booking.check_out_date >= check_out
                    ),
                    and_(
                        Booking.check_in_date >= check_in,
                        Booking.check_out_date <= check_out
                    )
                )
            ).count()
            
            available = total_rooms - booked_rooms
            
            if available > 0:
                # Calculate total price
                num_nights = (check_out - check_in).days
                total_price = float(room_type.base_price) * num_nights
                
                available_types.append({
                    **room_type.to_dict(),
                    'available_rooms': available,
                    'num_nights': num_nights,
                    'price_per_night': float(room_type.base_price),
                    'total_price': total_price
                })
        
        return jsonify({
            'hotel_id': hotel_id,
            'check_in_date': check_in.isoformat(),
            'check_out_date': check_out.isoformat(),
            'num_nights': (check_out - check_in).days,
            'num_guests': num_guests,
            'available_room_types': available_types
        }), 200
        
    except ValueError as e:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/', methods=['POST'])
def create_booking():
    """Create a new booking"""
    data = request.get_json()
    
    # Validate required fields
    required = [
        'hotel_id', 'room_type_id', 'check_in_date', 'check_out_date',
        'num_guests', 'guest_email', 'guest_first_name', 'guest_last_name',
        'guest_phone', 'total_amount'
    ]
    
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400
    
    try:
        # Parse dates
        check_in = datetime.strptime(data['check_in_date'], '%Y-%m-%d').date()
        check_out = datetime.strptime(data['check_out_date'], '%Y-%m-%d').date()
        
        # Create or get guest user
        from app.models.models import User, UserRole
        
        guest = User.query.filter_by(email=data['guest_email']).first()
        if not guest:
            guest = User(
                email=data['guest_email'],
                first_name=data['guest_first_name'],
                last_name=data['guest_last_name'],
                phone=data['guest_phone'],
                id_number=data.get('guest_id_number'),
                role=UserRole.FRONT_DESK  # Placeholder role for guests
            )
            db.session.add(guest)
            db.session.flush()  # Get guest.id
        
        # Create booking
        booking = Booking(
            hotel_id=data['hotel_id'],
            guest_id=guest.id,
            room_type_id=data['room_type_id'],
            check_in_date=check_in,
            check_out_date=check_out,
            num_guests=data['num_guests'],
            special_requests=data.get('special_requests'),
            total_amount=data['total_amount'],
            currency=data.get('currency', 'USD'),
            status=BookingStatus.PENDING
        )
        
        db.session.add(booking)
        db.session.commit()
        
        return jsonify({
            'message': 'Booking created successfully',
            'booking': booking.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:booking_id>', methods=['GET'])
def get_booking(booking_id):
    """Get booking details"""
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.is_deleted:
        return jsonify({'error': 'Booking not found'}), 404
    
    return jsonify(booking.to_dict()), 200


@bp.route('/<int:booking_id>/confirm', methods=['POST'])
def confirm_booking(booking_id):
    """Confirm booking after payment"""
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    try:
        booking.status = BookingStatus.CONFIRMED
        db.session.commit()
        
        # TODO: Send confirmation email
        
        return jsonify({
            'message': 'Booking confirmed',
            'booking': booking.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """Cancel a booking"""
    data = request.get_json()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    if booking.status == BookingStatus.CANCELLED:
        return jsonify({'error': 'Booking already cancelled'}), 400
    
    try:
        # Calculate cancellation charge
        charge = booking.calculate_cancellation_charge()
        refund = booking.total_amount - charge
        
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = datetime.utcnow()
        booking.cancellation_reason = data.get('reason')
        booking.refund_amount = refund
        
        db.session.commit()
        
        # TODO: Process refund through payment gateway
        
        return jsonify({
            'message': 'Booking cancelled',
            'cancellation_charge': float(charge),
            'refund_amount': float(refund),
            'booking': booking.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:booking_id>/checkin', methods=['POST'])
@token_required
def check_in(current_user, booking_id):
    """Check in a guest"""
    data = request.get_json()
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    if booking.status != BookingStatus.CONFIRMED:
        return jsonify({'error': 'Booking must be confirmed before check-in'}), 400
    
    try:
        # Assign room if not already assigned
        if not booking.room_id:
            room_id = data.get('room_id')
            if not room_id:
                # Auto-assign first available room of this type
                room = Room.query.filter_by(
                    hotel_id=booking.hotel_id,
                    room_type_id=booking.room_type_id,
                    status=RoomStatus.CLEAN_READY,
                    is_deleted=False
                ).first()
                
                if not room:
                    return jsonify({'error': 'No clean rooms available'}), 400
                    
                booking.room_id = room.id
            else:
                booking.room_id = room_id
        
        # Update booking
        booking.status = BookingStatus.CHECKED_IN
        booking.actual_check_in = datetime.utcnow()
        
        # Update room status
        room = Room.query.get(booking.room_id)
        room.status = RoomStatus.OCCUPIED
        
        db.session.commit()
        
        # TODO: Emit WebSocket event for real-time update
        
        return jsonify({
            'message': 'Check-in successful',
            'booking': booking.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:booking_id>/checkout', methods=['POST'])
@token_required
def check_out(current_user, booking_id):
    """Check out a guest"""
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    
    if booking.status != BookingStatus.CHECKED_IN:
        return jsonify({'error': 'Guest is not checked in'}), 400
    
    try:
        booking.status = BookingStatus.CHECKED_OUT
        booking.actual_check_out = datetime.utcnow()
        
        # Update room status to dirty
        if booking.room:
            booking.room.status = RoomStatus.VACANT_DIRTY
            
            # Create housekeeping task
            from app.models.booking import HousekeepingTask
            task = HousekeepingTask(
                room_id=booking.room_id,
                task_type='cleaning',
                priority='normal',
                status='pending'
            )
            db.session.add(task)
        
        db.session.commit()
        
        # TODO: Send feedback request email
        # TODO: Emit WebSocket event
        
        return jsonify({
            'message': 'Check-out successful',
            'booking': booking.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
