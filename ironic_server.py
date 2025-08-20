#!/var/lib/openstack/bin/python
import sys
import subprocess
from ironic.command.api import main as api

if __name__ == '__main__':
    if sys.argv[0].endswith('.exe'):
        sys.argv[0] = sys.argv[0][:-4]
    
    # Run database sync in a separate process to avoid oslo.config conflicts
    dbsync_cmd = [sys.executable, '-c', 
                  'from ironic.command.dbsync import main; import sys; sys.argv.extend(["create_schema"]); main()']
    
    try:
        result = subprocess.run(dbsync_cmd, check=True, capture_output=True, text=True)
        print("Database sync completed successfully")
        if result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Database sync failed: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        sys.exit(1)
    
    # Now start the API server
    sys.exit(api())
