class PhantomWallet {
    constructor() {
        this.provider = null;
        this.publicKey = null;
        this.isConnected = false;
        this.init();
    }

    async init() {
        this.checkPhantomAvailability();
        this.setupEventListeners();
        await this.checkExistingConnection();
    }

    checkPhantomAvailability() {
        if (window.solana && window.solana.isPhantom) {
            this.provider = window.solana;
            console.log('Phantom wallet detected');
        } else {
            console.warn('Phantom wallet not found');
            this.showError('Phantom wallet not found. Please install Phantom browser extension.');
        }
    }

    setupEventListeners() {
        const connectBtn = document.getElementById('connect-phantom');
        const disconnectBtn = document.getElementById('disconnect-phantom');
        
        if (connectBtn) {
            connectBtn.addEventListener('click', () => this.connect());
        }
        
        if (disconnectBtn) {
            disconnectBtn.addEventListener('click', () => this.disconnect());
        }

        // Listen for account changes
        if (this.provider) {
            this.provider.on('accountChanged', (publicKey) => {
                if (publicKey) {
                    this.publicKey = publicKey;
                    this.updateUI();
                } else {
                    this.disconnect();
                }
            });

            this.provider.on('disconnect', () => {
                this.disconnect();
            });
        }
    }

    async checkExistingConnection() {
        try {
            if (this.provider) {
                const response = await this.provider.connect({ onlyIfTrusted: true });
                if (response.publicKey) {
                    this.publicKey = response.publicKey;
                    this.isConnected = true;
                    this.updateUI();
                }
            }
        } catch (error) {
            console.log('No existing connection found');
        }
    }

    async connect() {
        if (!this.provider) {
            this.showError('Phantom wallet not available');
            return;
        }

        try {
            this.showLoading(true);
            const response = await this.provider.connect();
            
            if (response.publicKey) {
                this.publicKey = response.publicKey;
                this.isConnected = true;
                this.updateUI();
                this.showSuccess('Wallet connected successfully!');
                
                // Send connection info to backend
                await this.notifyBackend();
            }
        } catch (error) {
            console.error('Connection failed:', error);
            this.showError('Failed to connect wallet: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    async disconnect() {
        try {
            if (this.provider && this.isConnected) {
                await this.provider.disconnect();
            }
            
            this.publicKey = null;
            this.isConnected = false;
            this.updateUI();
            this.showSuccess('Wallet disconnected');
            
            // Notify backend of disconnection
            await this.notifyBackend();
        } catch (error) {
            console.error('Disconnect failed:', error);
            this.showError('Failed to disconnect wallet');
        }
    }

    async notifyBackend() {
        try {
            const response = await fetch('/api/wallet/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    public_key: this.publicKey ? this.publicKey.toString() : null,
                    is_connected: this.isConnected
                })
            });

            if (!response.ok) {
                throw new Error('Failed to update wallet status');
            }
        } catch (error) {
            console.error('Backend notification failed:', error);
        }
    }

    updateUI() {
        const connectBtn = document.getElementById('connect-phantom');
        const disconnectBtn = document.getElementById('disconnect-phantom');
        const walletInfo = document.getElementById('wallet-info');
        const walletAddress = document.getElementById('wallet-address');

        if (this.isConnected && this.publicKey) {
            // Show connected state
            if (connectBtn) connectBtn.style.display = 'none';
            if (disconnectBtn) disconnectBtn.style.display = 'inline-block';
            
            if (walletInfo) {
                walletInfo.style.display = 'block';
                if (walletAddress) {
                    walletAddress.textContent = this.truncateAddress(this.publicKey.toString());
                }
            }

            // Update any wallet-dependent buttons
            const walletButtons = document.querySelectorAll('.wallet-required');
            walletButtons.forEach(btn => {
                btn.disabled = false;
                btn.classList.remove('disabled');
            });
        } else {
            // Show disconnected state
            if (connectBtn) connectBtn.style.display = 'inline-block';
            if (disconnectBtn) disconnectBtn.style.display = 'none';
            
            if (walletInfo) walletInfo.style.display = 'none';

            // Disable wallet-dependent buttons
            const walletButtons = document.querySelectorAll('.wallet-required');
            walletButtons.forEach(btn => {
                btn.disabled = true;
                btn.classList.add('disabled');
            });
        }
    }

    truncateAddress(address) {
        if (!address) return '';
        return `${address.substring(0, 4)}...${address.substring(address.length - 4)}`;
    }

    showLoading(show) {
        const connectBtn = document.getElementById('connect-phantom');
        if (connectBtn) {
            if (show) {
                connectBtn.disabled = true;
                connectBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Connecting...';
            } else {
                connectBtn.disabled = false;
                connectBtn.innerHTML = '<i class="fab fa-phantom"></i> Connect Phantom';
            }
        }
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="close-btn">&times;</button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Remove after delay
        setTimeout(() => {
            notification.remove();
        }, 5000);

        // Add close functionality
        notification.querySelector('.close-btn').addEventListener('click', () => {
            notification.remove();
        });
    }

    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }

    // Public methods for external use
    getPublicKey() {
        return this.publicKey;
    }

    getIsConnected() {
        return this.isConnected;
    }

    async signTransaction(transaction) {
        if (!this.provider || !this.isConnected) {
            throw new Error('Wallet not connected');
        }
        return await this.provider.signTransaction(transaction);
    }

    async signMessage(message) {
        if (!this.provider || !this.isConnected) {
            throw new Error('Wallet not connected');
        }
        return await this.provider.signMessage(message);
    }
}

// Initialize wallet when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.phantomWallet = new PhantomWallet();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PhantomWallet;
}