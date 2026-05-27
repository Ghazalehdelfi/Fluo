Deployment Steps (in order)
1. Create Lightsail instance (AWS Console)

Ubuntu 22.04, $5/mo plan
Attach a static IP
Open ports 80 and 443 in networking tab
Download the SSH key
2. Upload secrets to SSM (from your Mac)

3. SSH into the instance and run setup

4. For future code updates (from your Mac)

5. Optional: Add HTTPS (on the server, after pointing your domain)

Your secrets never touch the disk on the server — they're fetched from SSM Parameter Store at each app startup.