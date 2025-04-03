import subprocess
import time
import datetime
import os

def run_commands_from_file(input_file, log_file, interval_minutes=1):
    """
    Execute commands from a file with specified interval and log output
    
    Args:
        input_file (str): Path to file containing commands
        log_file (str): Path to log file
        interval_minutes (int): Interval between commands in minutes
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Open log file in append mode
    with open(log_file, 'a', encoding='utf-8') as log:
        # Write header with timestamp
        log.write(f"\n{'='*80}\n")
        log.write(f"Execution started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"{'='*80}\n\n")
        
        # Read and execute commands
        with open(input_file, 'r') as f:
            commands = f.readlines()
            
        for i, cmd in enumerate(commands, 1):
            cmd = cmd.strip()
            if not cmd or cmd.startswith('#'):
                continue
                
            # Log command start
            log.write(f"\n{'='*80}\n")
            log.write(f"Executing command {i}/{len(commands)}: {cmd}\n")
            log.write(f"Start time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.write(f"{'='*80}\n\n")
            
            try:
                # Execute command and capture output
                result = subprocess.run(
                    cmd,
                    shell=True,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Log successful output
                log.write(f"Command output:\n{result.stdout}\n")
                if result.stderr:
                    log.write(f"Command stderr:\n{result.stderr}\n")
                    
            except subprocess.CalledProcessError as e:
                # Log error
                log.write(f"Error executing command: {e}\n")
                log.write(f"Error output:\n{e.stderr}\n")
                
            except Exception as e:
                # Log unexpected errors
                log.write(f"Unexpected error: {str(e)}\n")
                
            # Log command end
            log.write(f"\n{'='*80}\n")
            log.write(f"Command {i} completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.write(f"{'='*80}\n\n")
            
            # Wait for specified interval (except after last command)
            if i < len(commands):
                log.write(f"Waiting {interval_minutes} minute(s) before next command...\n")
                time.sleep(interval_minutes * 60)
                
        # Write footer
        log.write(f"\n{'='*80}\n")
        log.write(f"All commands completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log.write(f"{'='*80}\n\n")

if __name__ == "__main__":
    # Configuration
    INPUT_FILE = "commands.txt"  # File containing commands to execute
    LOG_FILE = "execution_output.log"  # Log file path
    INTERVAL_MINUTES = 1  # Interval between commands in minutes
    
    # Run the commands
    run_commands_from_file(INPUT_FILE, LOG_FILE, INTERVAL_MINUTES)
