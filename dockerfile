FROM debian:bookworm-slim

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcupsimage2 \
    cups \
    libcups2 \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy fonts
COPY fonts /usr/share/fonts/truetype/custom

# Copy app code
WORKDIR /app
COPY . /app

# Install CUPS printer driver
WORKDIR /app/printer/driver
RUN chmod +x Install.sh && ./Install.sh

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Expose CUPS and app ports
EXPOSE 631
EXPOSE 8000