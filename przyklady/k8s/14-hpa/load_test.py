#!/usr/bin/env python3

import requests
import time
import threading
import argparse
import signal
import random
import string
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Konfiguracja sesji z retry
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def generate_random_data(size_kb):
    """Generuje losowe dane o określonym rozmiarze."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size_kb * 1024))

def make_request(url, session, method='GET'):
    """Wykonuje zapytanie HTTP z różnymi metodami i danymi."""
    try:
        if method == 'GET':
            # Dodaj losowe parametry do URL
            params = {
                'cache': random.randint(1, 1000),
                'timestamp': int(time.time() * 1000)
            }
            response = session.get(url, params=params, timeout=5)
        elif method == 'POST':
            # Wyślij losowe dane
            data = generate_random_data(random.randint(1, 10))  # 1-10KB danych
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            response = session.post(url, data=data, headers=headers, timeout=5)
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Błąd podczas wykonywania zapytania: {e}")
        return None

def load_test(url, num_requests, concurrency, duration):
    """Wykonuje test obciążeniowy."""
    print(f"Rozpoczynam test obciążeniowy:")
    print(f"- URL: {url}")
    print(f"- Liczba równoległych wątków: {concurrency}")
    print(f"- Czas trwania testu: {duration} sekund")
    
    start_time = time.time()
    end_time = start_time + duration
    total_requests = 0
    successful_requests = 0
    failed_requests = 0
    
    # Flaga do kontroli przerwania testu
    stop_test = threading.Event()
    
    def signal_handler(signum, frame):
        print("\nOtrzymano sygnał przerwania. Kończę test...")
        stop_test.set()
    
    # Rejestracja handlera dla SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, signal_handler)
    
    session = create_session()
    
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            while time.time() < end_time and not stop_test.is_set():
                # Mieszaj metody GET i POST
                futures = []
                for _ in range(concurrency):
                    method = random.choice(['GET', 'POST'])
                    futures.append(executor.submit(make_request, url, session, method))
                
                for future in futures:
                    try:
                        result = future.result(timeout=10)
                        total_requests += 1
                        if result == 200:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                    except Exception as e:
                        print(f"Błąd podczas przetwarzania zapytania: {e}")
                        failed_requests += 1
                
                # Wyświetl postęp co 5 sekund
                elapsed = time.time() - start_time
                if int(elapsed) % 5 == 0:
                    print(f"\nPostęp testu ({int(elapsed)}s):")
                    print(f"- Wykonano zapytań: {total_requests}")
                    print(f"- Udanych zapytań: {successful_requests}")
                    print(f"- Nieudanych zapytań: {failed_requests}")
                    print(f"- RPS: {total_requests/elapsed:.2f}")
                
                # Minimalne opóźnienie między partiami
                time.sleep(0.01)
    
    except KeyboardInterrupt:
        print("\nTest przerwany przez użytkownika")
    finally:
        # Podsumowanie
        total_time = time.time() - start_time
        print("\nPodsumowanie testu:")
        print(f"- Całkowity czas: {total_time:.2f} sekund")
        print(f"- Całkowita liczba zapytań: {total_requests}")
        print(f"- Udane zapytania: {successful_requests}")
        print(f"- Nieudane zapytania: {failed_requests}")
        print(f"- Średni RPS: {total_requests/total_time:.2f}")
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Generator obciążenia dla testów HPA')
    parser.add_argument('--url', required=True, help='URL do testowania')
    parser.add_argument('--concurrency', type=int, default=100, help='Liczba równoległych wątków')
    parser.add_argument('--duration', type=int, default=300, help='Czas trwania testu w sekundach')
    
    args = parser.parse_args()
    
    load_test(args.url, args.concurrency, args.concurrency, args.duration)

if __name__ == "__main__":
    main() 