import multiprocessing
import time
import os
import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Function timed out!")

def run_with_timeout(timeout, func):
    # Use signal-based timeout on Unix-like systems
    if os.name == 'posix':
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)  # Schedule the timeout alarm
        try:
            func()
            signal.alarm(0)  # Cancel alarm if function completed in time
        except TimeoutException:
            print("Function timed out!")
        except Exception as e:
            signal.alarm(0)
            raise e
    else:
        # Fallback: use multiprocessing with a Queue to capture the result
        process = multiprocessing.Process(target=func)
        process.start()
        process.join(timeout)

        if process.is_alive():
            process.terminate()  # Kill the function if timeout exceeded
            process.join()
            # self.did_timeout = True
        
        process.close()  # Clean up the process

def my_function():
    time.sleep(2)
    print("Sleep completed")

def main():
    run_with_timeout(1, my_function)  # Expected to timeout on Unix systems
    run_with_timeout(3, my_function)  # Expected to complete successfully

if __name__ == '__main__':
    main()