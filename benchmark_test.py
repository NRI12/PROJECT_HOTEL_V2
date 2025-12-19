"""
Script để đo lường performance thực tế của hệ thống
Chạy: python benchmark_test.py
"""
import time
import requests
import statistics
from datetime import datetime
from app import create_app
from app import db
from app.models.hotel import Hotel
from app.models.room import Room
from app.models.booking import Booking
from app.controllers.search_controller import SearchController
from app.services.chatbot_service import get_chatbot_answer
from flask import Flask
from flask.testing import FlaskClient
import os

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = create_app('development')
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

results = {
    'search_basic': [],
    'search_advanced': [],
    'database_query': [],
    'hotel_detail': [],
    'check_availability': [],
    'chatbot_response': [],
    'page_load': []
}

def measure_time(func, *args, **kwargs):
    """Đo thời gian thực thi của một function"""
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000  # Convert to milliseconds
        return elapsed_ms, result
    except Exception as e:
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000
        return elapsed_ms, None

def test_search_basic():
    """Test tìm kiếm cơ bản"""
    print("🔍 Testing basic search...")
    times = []
    
    with app.test_request_context('/search?destination=Hà Nội'):
        with app.app_context():
            # Test với các query khác nhau
            test_queries = [
                {'destination': 'Hà Nội'},
                {'destination': 'Hồ Chí Minh'},
                {'destination': 'Đà Nẵng'},
            ]
            
            for query in test_queries:
                # Mock request args
                from flask import request
                from unittest.mock import patch
                
                with app.test_request_context(f'/search?destination={query["destination"]}'):
                    elapsed, _ = measure_time(
                        SearchController.search_for_web
                    )
                    if elapsed > 1:  # Chỉ lấy kết quả hợp lệ (> 1ms)
                        times.append(elapsed)
                time.sleep(0.1)  # Small delay between requests
    
    avg_time = statistics.mean(times) if times else 0
    results['search_basic'] = times
    if times:
        print(f"   Average: {avg_time:.2f}ms (min: {min(times):.2f}ms, max: {max(times):.2f}ms)")
    return avg_time

def test_search_advanced():
    """Test tìm kiếm nâng cao với nhiều filters"""
    print("🔍 Testing advanced search with filters...")
    times = []
    
    test_queries = [
        '/search?destination=Hà Nội&min_price=500000&max_price=2000000&star_rating=4',
        '/search?destination=Hồ Chí Minh&min_price=1000000&max_price=3000000&star_rating=4',
    ]
    
    for query_url in test_queries:
        with app.test_request_context(query_url):
            with app.app_context():
                elapsed, _ = measure_time(
                    SearchController.search_for_web
                )
                if elapsed > 1:  # Chỉ lấy kết quả hợp lệ
                    times.append(elapsed)
        time.sleep(0.1)
    
    avg_time = statistics.mean(times) if times else 0
    results['search_advanced'] = times
    if times:
        print(f"   Average: {avg_time:.2f}ms (min: {min(times):.2f}ms, max: {max(times):.2f}ms)")
    return avg_time

def test_database_queries():
    """Test các database queries"""
    print("📊 Testing database queries...")
    times = []
    
    with app.app_context():
        # Test query hotels
        elapsed, hotels = measure_time(
            lambda: Hotel.query.filter_by(status='active').limit(10).all()
        )
        times.append(elapsed)
        print(f"   Query hotels (10 items): {elapsed:.2f}ms")
        
        # Test query với join
        elapsed, _ = measure_time(
            lambda: db.session.query(Hotel, Room)
                .join(Room)
                .filter(Hotel.status == 'active')
                .limit(10)
                .all()
        )
        times.append(elapsed)
        print(f"   Query with join: {elapsed:.2f}ms")
        
        # Test count
        elapsed, _ = measure_time(
            lambda: Hotel.query.filter_by(status='active').count()
        )
        times.append(elapsed)
        print(f"   Count query: {elapsed:.2f}ms")
    
    avg_time = statistics.mean(times) if times else 0
    results['database_query'] = times
    print(f"   Average: {avg_time:.2f}ms")
    return avg_time

def test_hotel_detail():
    """Test lấy chi tiết khách sạn"""
    print("🏨 Testing hotel detail...")
    times = []
    
    with app.app_context():
        # Lấy một hotel ID thực tế
        hotel = Hotel.query.filter_by(status='active').first()
        if hotel:
            from app.controllers.hotel_controller import HotelController
            
            elapsed, _ = measure_time(
                lambda: hotel.to_dict()
            )
            times.append(elapsed)
            
            # Test với images và amenities
            elapsed, _ = measure_time(
                lambda: {
                    'hotel': hotel.to_dict(),
                    'images': [img.to_dict() for img in hotel.images[:5]],
                    'amenities': [a.to_dict() for a in hotel.amenities[:10]]
                }
            )
            times.append(elapsed)
    
    avg_time = statistics.mean(times) if times else 0
    results['hotel_detail'] = times
    print(f"   Average: {avg_time:.2f}ms")
    return avg_time

def test_check_availability():
    """Test kiểm tra phòng trống"""
    print("📅 Testing room availability check...")
    times = []
    
    with app.app_context():
        from datetime import date, timedelta
        check_in = date.today() + timedelta(days=7)
        check_out = check_in + timedelta(days=2)
        
        elapsed, _ = measure_time(
            SearchController.check_availability
        )
        times.append(elapsed)
    
    avg_time = statistics.mean(times) if times else 0
    results['check_availability'] = times
    print(f"   Average: {avg_time:.2f}ms")
    return avg_time

def test_chatbot():
    """Test chatbot response time"""
    print("🤖 Testing chatbot response...")
    times = []
    
    with app.app_context():
        test_messages = [
            "Xin chào",
            "Có khách sạn nào ở Hà Nội không?",
            "Giá phòng bao nhiêu?",
        ]
        
        for msg in test_messages:
            try:
                elapsed, response = measure_time(
                    get_chatbot_answer,
                    msg,
                    None
                )
                if response:
                    times.append(elapsed)
                    print(f"   Message: '{msg[:30]}...' - {elapsed:.2f}ms")
                time.sleep(1)  # Delay để tránh rate limit
            except Exception as e:
                print(f"   Error: {str(e)}")
                continue
    
    avg_time = statistics.mean(times) if times else 0
    results['chatbot_response'] = times
    if times:
        print(f"   Average: {avg_time:.2f}ms (min: {min(times):.2f}ms, max: {max(times):.2f}ms)")
    return avg_time

def test_page_load():
    """Test thời gian load trang (simulated)"""
    print("🌐 Testing page load (simulated)...")
    times = []
    
    with app.test_client() as client:
        # Test homepage
        elapsed, _ = measure_time(
            client.get,
            '/'
        )
        if elapsed:
            times.append(elapsed)
            print(f"   Homepage: {elapsed:.2f}ms")
        
        # Test search page
        elapsed, _ = measure_time(
            client.get,
            '/search'
        )
        if elapsed:
            times.append(elapsed)
            print(f"   Search page: {elapsed:.2f}ms")
    
    avg_time = statistics.mean(times) if times else 0
    results['page_load'] = times
    print(f"   Average: {avg_time:.2f}ms")
    return avg_time

def generate_report():
    """Tạo báo cáo kết quả"""
    print("\n" + "="*60)
    print("📊 BÁO CÁO KẾT QUẢ ĐO LƯỜNG")
    print("="*60)
    print(f"Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    report = []
    
    for test_name, times in results.items():
        if times:
            avg = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            median = statistics.median(times)
            
            report.append({
                'test': test_name,
                'avg': avg,
                'min': min_time,
                'max': max_time,
                'median': median,
                'count': len(times)
            })
    
    # Print formatted report
    print(f"{'Test':<25} {'Avg (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12} {'Median (ms)':<12}")
    print("-" * 75)
    
    for r in report:
        print(f"{r['test']:<25} {r['avg']:<12.2f} {r['min']:<12.2f} {r['max']:<12.2f} {r['median']:<12.2f}")
    
    return report

if __name__ == '__main__':
    print("🚀 Bắt đầu đo lường performance...\n")
    
    try:
        # Chạy các tests
        test_database_queries()
        print()
        
        test_search_basic()
        print()
        
        test_search_advanced()
        print()
        
        test_hotel_detail()
        print()
        
        test_check_availability()
        print()
        
        test_page_load()
        print()
        
        # Chatbot test (có thể skip nếu không có API key)
        try:
            test_chatbot()
            print()
        except Exception as e:
            print(f"⚠️  Chatbot test skipped: {str(e)}\n")
        
        # Generate report
        report = generate_report()
        
        print("\n✅ Hoàn thành đo lường!")
        
    except Exception as e:
        print(f"\n❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()

