import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def provision_ssl(domain_name, extension):
    full_domain = f"{domain_name}.{extension}"
    www_domain = f"www.{full_domain}"
    
    # 1. Create Nginx config
    nginx_config = f"""server {{
    listen 80;
    server_name {full_domain} {www_domain};

    location / {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
    
    try:
        # Write to a temporary file first
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(nginx_config)
            tmp_path = tmp.name
        
        # Move to sites-available (requires sudo)
        sites_available = f"/etc/nginx/sites-available/{full_domain}"
        sites_enabled = f"/etc/nginx/sites-enabled/{full_domain}"
        
        subprocess.run(['sudo', 'mv', tmp_path, sites_available], check=True)
        
        # Create symlink if it doesn't exist
        subprocess.run(['sudo', 'ln', '-sf', sites_available, sites_enabled], check=True)
        
        # Reload Nginx
        subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
        
        # 2. Run Certbot
        certbot_cmd = [
            'sudo', 'certbot', '--nginx',
            '-d', full_domain,
            '-d', www_domain,
            '--non-interactive',
            '--agree-tos',
            '-m', 'admin@flezpay.com',
            '--redirect'
        ]
        
        result = subprocess.run(certbot_cmd, capture_output=True, text=True, check=True)
        logger.info(f"Certbot successful for {full_domain}: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to provision SSL for {full_domain}. Error: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during SSL provisioning for {full_domain}: {str(e)}")
        return False
