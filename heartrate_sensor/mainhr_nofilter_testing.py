import time
import argparse
from heartrate_no_filters import HeartRateMonitor  

def main():
    parser = argparse.ArgumentParser(
        description="Simple raw heart rate data collector"
    )
    parser.add_argument(
        "-t", "--time", 
        type=int, 
        default=10,
        help="Duration in seconds (default: 10)"
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="raw_heartrate_data.csv",
        help="Output CSV filename"
    )
    
    args = parser.parse_args()
    
    print("Starting MAX30102 raw data collection...")
    print(f"Will collect for {args.time} seconds")
    print("Press Ctrl+C to stop early\n")
    
    # Create and start sensor
    hrm = HeartRateMonitor(fs=100)
    hrm.start_sensor()
    
    try:
        # Wait for specified time
        for i in range(args.time):
            print(f"Time remaining: {args.time - i} seconds", end='\r')
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        # Stop sensor
        hrm.stop_sensor()
        print("\nSensor stopped")
    
    # Save data
    if hrm.raw_data:
        hrm.export_to_csv(args.output)
        print(f"\nSaved {len(hrm.raw_data)} samples to {args.output}")
    else:
        print("\nNo data collected")
    
    print("Done!")

if __name__ == "__main__":
    main()