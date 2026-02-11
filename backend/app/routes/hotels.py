"""Hotel routes"""
from flask import Blueprint, request, jsonify
from app.models.models import Hotel, RoomType

bp = Blueprint('hotels', __name__)

@bp.route('/', methods=['GET'])
def get_hotels():
    """Get all hotels"""
    hotels = Hotel.query.filter_by(is_deleted=False).all()
    return jsonify([hotel.to_dict() for hotel in hotels]), 200

@bp.route('/<int:hotel_id>', methods=['GET'])
def get_hotel(hotel_id):
    """Get hotel details"""
    hotel = Hotel.query.get(hotel_id)
    if not hotel or hotel.is_deleted:
        return jsonify({'error': 'Hotel not found'}), 404
    
    # Include room types
    room_types = RoomType.query.filter_by(hotel_id=hotel_id, is_deleted=False).all()
    hotel_data = hotel.to_dict()
    hotel_data['room_types'] = [rt.to_dict() for rt in room_types]
    
    return jsonify(hotel_data), 200
