import redis
from rq import SimpleWorker


if __name__ == '__main__':
    print("[WORKER] Starting Redis Queue worker...")
    
    # Connect to Redis
    redis_conn = redis.Redis()
    print("[WORKER] Connected to Redis")

    # Use SimpleWorker which doesn't fork processes
    worker = SimpleWorker(queues=["default"], connection=redis_conn)
    print("[WORKER] SimpleWorker initialized, waiting for jobs...")

    # Start processing jobs
    worker.work()
