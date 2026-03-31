/**
 * Crypto Payment Integration for ResonantOS Dashboard
 * Handles Solana-based payments for add-ons and subscriptions
 */

// ============================================
// Configuration
// ============================================

const CRYPTO_CONFIG = {
    // Add-on pricing in USD
    addons: {
        watermark: {
            id: 'watermark',
            name: 'Remove Watermark',
            description: 'Remove ResonantOS branding from your chatbot',
            priceUsd: 10,
            icon: '✨'
        },
        extra_chatbot: {
            id: 'extra_chatbot',
            name: 'Extra Chatbot',
            description: 'Add one more chatbot slot to your account',
            priceUsd: 15,
            icon: '🤖'
        },
        custom_icon: {
            id: 'custom_icon',
            name: 'Custom Icon',
            description: 'Use your own custom icon/avatar',
            priceUsd: 5,
            icon: '🎨'
        },
        analytics: {
            id: 'analytics',
            name: 'Advanced Analytics',
            description: 'Detailed analytics and insights',
            priceUsd: 20,
            icon: '📊'
        }
    },
    
    // Subscription tiers
    tiers: {
        essential: {
            id: 'essential',
            name: 'Essential',
            description: 'Remove watermark + custom icon',
            priceUsd: 10,
            icon: '⭐'
        },
        professional: {
            id: 'professional',
            name: 'Professional',
            description: '5 chatbots + all features',
            priceUsd: 50,
            icon: '💼'
        },
        business: {
            id: 'business',
            name: 'Business',
            description: 'Unlimited chatbots + priority support',
            priceUsd: 150,
            icon: '🏢'
        }
    },
    
    // Supported chains and tokens
    chains: {
        solana: {
            name: 'Solana',
            tokens: ['SOL', 'USDT', 'USDC'],
            icon: '◎'
        },
        bitcoin: {
            name: 'Bitcoin',
            tokens: ['BTC'],
            icon: '₿'
        },
        ethereum: {
            name: 'Ethereum',
            tokens: ['ETH', 'USDT', 'USDC'],
            icon: 'Ξ'
        }
    },
    
    // Payment check interval (ms)
    pollInterval: 5000,
    
    // Payment expiry (30 minutes)
    expiryMinutes: 30
};

// ============================================
// State
// ============================================

let currentPayment = null;
let paymentPollInterval = null;

// ============================================
// Payment Flow
// ============================================

/**
 * Initialize crypto payment for an add-on or tier
 */
async function initCryptoPayment(productId, durationMonths = 1, chain = 'solana', token = 'SOL') {
    // Check if it's an addon or tier
    const product = CRYPTO_CONFIG.addons[productId] || CRYPTO_CONFIG.tiers[productId];
    if (!product) {
        showToast('Invalid product selected', 'error');
        return;
    }
    
    try {
        // Show loading state
        showPaymentModal(product, durationMonths, 'loading', { chain, token });
        
        // Request payment details from server
        const response = await fetch('/api/crypto/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                add_on: productId,
                duration_months: durationMonths,
                chain: chain,
                token: token
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to create payment');
        }
        
        const paymentData = await response.json();
        currentPayment = paymentData;
        
        // Update modal with payment details
        showPaymentModal(product, durationMonths, 'waiting', paymentData);
        
        // Start polling for payment
        startPaymentPolling(paymentData.payment_id);
        
    } catch (error) {
        console.error('Crypto payment error:', error);
        showPaymentModal(product, durationMonths, 'error', { error: error.message });
    }
}

/**
 * Start polling for payment confirmation
 */
function startPaymentPolling(paymentId) {
    // Clear any existing interval
    if (paymentPollInterval) {
        clearInterval(paymentPollInterval);
    }
    
    paymentPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/crypto/status?payment_id=${paymentId}`);
            const status = await response.json();
            
            if (status.status === 'confirmed') {
                clearInterval(paymentPollInterval);
                paymentPollInterval = null;
                onPaymentConfirmed(status);
            } else if (status.status === 'expired') {
                clearInterval(paymentPollInterval);
                paymentPollInterval = null;
                onPaymentExpired();
            }
            
            // Update time remaining
            if (status.expires_at && currentPayment) {
                const remaining = new Date(status.expires_at) - new Date();
                if (remaining > 0) {
                    updateTimeRemaining(remaining);
                }
            }
            
        } catch (error) {
            console.error('Payment poll error:', error);
        }
    }, CRYPTO_CONFIG.pollInterval);
}

/**
 * Stop payment polling
 */
function stopPaymentPolling() {
    if (paymentPollInterval) {
        clearInterval(paymentPollInterval);
        paymentPollInterval = null;
    }
}

/**
 * Manually verify a transaction
 */
async function verifyTransaction(txSignature) {
    if (!currentPayment) {
        showToast('No active payment to verify', 'error');
        return;
    }
    
    try {
        showToast('Verifying transaction...', 'info');
        
        const response = await fetch('/api/crypto/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                payment_id: currentPayment.payment_id,
                tx_signature: txSignature
            })
        });
        
        const result = await response.json();
        
        if (result.verified) {
            stopPaymentPolling();
            onPaymentConfirmed(result);
        } else {
            showToast(result.error || 'Transaction could not be verified', 'error');
        }
        
    } catch (error) {
        console.error('Verification error:', error);
        showToast('Failed to verify transaction', 'error');
    }
}

/**
 * Handle confirmed payment
 */
function onPaymentConfirmed(data) {
    currentPayment = null;
    
    // Update modal to success state
    const modalBody = document.querySelector('#cryptoPaymentModal .modal-body');
    if (modalBody) {
        modalBody.innerHTML = `
            <div class="payment-success">
                <div class="success-icon">✅</div>
                <h3>Payment Confirmed!</h3>
                <p>Your add-on has been activated.</p>
                ${data.tx_signature ? `
                    <div class="tx-details">
                        <span class="label">Transaction:</span>
                        <a href="https://explorer.solana.com/tx/${data.tx_signature}?cluster=devnet" 
                           target="_blank" class="tx-link">
                            ${data.tx_signature.substring(0, 16)}...
                        </a>
                    </div>
                ` : ''}
                <p class="success-note">License active until: ${data.license_expires || 'N/A'}</p>
            </div>
        `;
    }
    
    // Update footer
    const modalFooter = document.querySelector('#cryptoPaymentModal .modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button class="btn-primary" onclick="closeCryptoPaymentModal()">Done</button>
        `;
    }
    
    showToast('Payment confirmed! Add-on activated.', 'success');
    
    // Refresh add-ons list after a short delay
    setTimeout(() => {
        if (typeof loadAddons === 'function') {
            loadAddons();
        }
    }, 1000);
}

/**
 * Handle expired payment
 */
function onPaymentExpired() {
    currentPayment = null;
    
    const modalBody = document.querySelector('#cryptoPaymentModal .modal-body');
    if (modalBody) {
        modalBody.innerHTML = `
            <div class="payment-expired">
                <div class="expired-icon">⏰</div>
                <h3>Payment Expired</h3>
                <p>The payment window has expired. Please try again.</p>
            </div>
        `;
    }
    
    const modalFooter = document.querySelector('#cryptoPaymentModal .modal-footer');
    if (modalFooter) {
        modalFooter.innerHTML = `
            <button class="btn-secondary" onclick="closeCryptoPaymentModal()">Close</button>
            <button class="btn-primary" onclick="closeCryptoPaymentModal(); location.reload();">Try Again</button>
        `;
    }
    
    showToast('Payment expired. Please try again.', 'warning');
}

/**
 * Update time remaining display
 */
function updateTimeRemaining(remainingMs) {
    const el = document.getElementById('paymentTimeRemaining');
    if (!el) return;
    
    const minutes = Math.floor(remainingMs / 60000);
    const seconds = Math.floor((remainingMs % 60000) / 1000);
    
    el.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    
    if (minutes < 5) {
        el.classList.add('urgent');
    }
}

// ============================================
// Modal Management
// ============================================

/**
 * Show payment modal with current state (multi-chain support)
 */
function showPaymentModal(product, durationMonths, state, data = {}) {
    let modal = document.getElementById('cryptoPaymentModal');
    
    // Create modal if it doesn't exist
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'cryptoPaymentModal';
        modal.className = 'modal';
        document.body.appendChild(modal);
    }
    
    const totalUsd = product.priceUsd * durationMonths;
    const chain = data.chain || 'solana';
    const token = data.token || 'SOL';
    const chainInfo = CRYPTO_CONFIG.chains[chain] || CRYPTO_CONFIG.chains.solana;
    
    let bodyContent = '';
    let footerContent = '';
    
    switch (state) {
        case 'loading':
            bodyContent = `
                <div class="payment-loading">
                    <div class="loader"></div>
                    <p>Preparing ${token} payment on ${chainInfo.name}...</p>
                </div>
            `;
            footerContent = `
                <button class="btn-secondary" onclick="closeCryptoPaymentModal()">Cancel</button>
            `;
            break;
            
        case 'waiting':
            const amountCrypto = data.amount_crypto || data.amount_sol || 0;
            const tokenPrice = data.token_price_usd || data.sol_price_usd || 0;
            
            bodyContent = `
                <div class="payment-details">
                    <div class="addon-summary">
                        <span class="addon-icon">${product.icon}</span>
                        <div class="addon-info">
                            <h3>${product.name}</h3>
                            <p>${durationMonths} month${durationMonths > 1 ? 's' : ''}</p>
                        </div>
                    </div>
                    
                    <div class="chain-badge">
                        <span class="chain-icon">${chainInfo.icon}</span>
                        <span class="chain-name">${chainInfo.name}</span>
                        <span class="token-name">${token}</span>
                    </div>
                    
                    <div class="payment-amount">
                        <div class="amount-crypto">
                            <span class="amount-value">${amountCrypto}</span>
                            <span class="amount-symbol">${token}</span>
                        </div>
                        <div class="amount-usd">≈ $${totalUsd.toFixed(2)} USD</div>
                        ${!['USDT', 'USDC'].includes(token) ? `
                            <div class="token-price">1 ${token} ≈ $${tokenPrice?.toFixed(2) || '---'}</div>
                        ` : ''}
                    </div>
                    
                    <div class="payment-address-section">
                        <label>Send ${token} to this ${chainInfo.name} address:</label>
                        <div class="address-box">
                            <code id="paymentAddress">${data.payment_address}</code>
                            <button class="copy-btn" onclick="copyPaymentAddress()">📋</button>
                        </div>
                    </div>
                    
                    <div class="qr-code-section">
                        <div class="qr-container" id="paymentQR">
                            ${generateQRCode(data.payment_address, 180)}
                        </div>
                        <p class="qr-hint">Scan with your ${chainInfo.name} wallet</p>
                    </div>
                    
                    <div class="payment-status">
                        <div class="status-indicator waiting">
                            <span class="pulse-dot"></span>
                            <span>Waiting for payment...</span>
                        </div>
                        <div class="time-remaining">
                            Expires in: <span id="paymentTimeRemaining">${CRYPTO_CONFIG.expiryMinutes}:00</span>
                        </div>
                    </div>
                    
                    <div class="manual-verify">
                        <details>
                            <summary>Already sent? Enter transaction ${chain === 'bitcoin' ? 'ID' : 'signature'}</summary>
                            <div class="verify-input">
                                <input type="text" id="txSignatureInput" 
                                       placeholder="Transaction ${chain === 'bitcoin' ? 'ID' : 'signature'}...">
                                <button class="btn-small" onclick="manualVerify()">Verify</button>
                            </div>
                        </details>
                    </div>
                </div>
            `;
            footerContent = `
                <button class="btn-secondary" onclick="closeCryptoPaymentModal()">Cancel</button>
                <div class="network-badge ${chain}">${data.network || 'testnet'}</div>
            `;
            break;
            
        case 'error':
            bodyContent = `
                <div class="payment-error">
                    <div class="error-icon">❌</div>
                    <h3>Payment Error</h3>
                    <p>${data.error || 'An error occurred while creating the payment.'}</p>
                </div>
            `;
            footerContent = `
                <button class="btn-secondary" onclick="closeCryptoPaymentModal()">Close</button>
                <button class="btn-primary" onclick="closeCryptoPaymentModal(); initCryptoPayment('${product.id}', ${durationMonths}, '${chain}', '${token}');">Retry</button>
            `;
            break;
    }
    
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>${chainInfo.icon} Pay with ${token}</h2>
                <button class="modal-close" onclick="closeCryptoPaymentModal()">&times;</button>
            </div>
            <div class="modal-body">
                ${bodyContent}
            </div>
            <div class="modal-footer">
                ${footerContent}
            </div>
        </div>
    `;
    
    modal.classList.add('active');
}

/**
 * Close payment modal
 */
function closeCryptoPaymentModal() {
    const modal = document.getElementById('cryptoPaymentModal');
    if (modal) {
        modal.classList.remove('active');
    }
    stopPaymentPolling();
    currentPayment = null;
}

/**
 * Copy payment address to clipboard
 */
function copyPaymentAddress() {
    const address = document.getElementById('paymentAddress')?.textContent;
    if (address) {
        navigator.clipboard.writeText(address);
        showToast('Address copied to clipboard!', 'success');
    }
}

/**
 * Manual transaction verification
 */
function manualVerify() {
    const input = document.getElementById('txSignatureInput');
    const signature = input?.value?.trim();
    
    if (!signature) {
        showToast('Please enter a transaction signature', 'warning');
        return;
    }
    
    verifyTransaction(signature);
}

/**
 * Generate QR code using canvas API (no external dependencies)
 */
function generateQRCode(address, size = 180) {
    // Use a simple QR code API service for reliability
    const qrApiUrl = `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(address)}&bgcolor=1a1a1a&color=4ade80`;
    
    return `
        <img src="${qrApiUrl}" alt="QR Code" class="qr-image" 
             onerror="this.onerror=null; this.parentElement.innerHTML = generateQRFallback('${address}');" />
    `;
}

/**
 * Fallback QR display if API fails
 */
function generateQRFallback(address) {
    return `
        <div class="qr-mock">
            <div class="qr-icon">📱</div>
            <div class="qr-address-short">${address?.substring(0, 8)}...${address?.substring(address.length - 8)}</div>
            <div class="qr-manual-hint">Copy address above to send payment</div>
        </div>
    `;
}

// Expose fallback globally for onerror
window.generateQRFallback = generateQRFallback;

// ============================================
// Payment Choice Modal
// ============================================

/**
 * Show payment method selection modal (with multi-chain crypto)
 */
function showPaymentChoice(productId, durationMonths = 1) {
    // Check both addons and tiers
    const product = CRYPTO_CONFIG.addons[productId] || CRYPTO_CONFIG.tiers[productId];
    if (!product) {
        showToast('Invalid product', 'error');
        return;
    }
    
    let modal = document.getElementById('paymentChoiceModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'paymentChoiceModal';
        modal.className = 'modal';
        document.body.appendChild(modal);
    }
    
    const totalUsd = product.priceUsd * durationMonths;
    
    modal.innerHTML = `
        <div class="modal-content payment-choice-modal">
            <div class="modal-header">
                <h2>Choose Payment Method</h2>
                <button class="modal-close" onclick="closePaymentChoiceModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="addon-summary centered">
                    <span class="addon-icon large">${product.icon}</span>
                    <h3>${product.name}</h3>
                    <p>${product.description}</p>
                    <div class="price-display">
                        <span class="price">$${totalUsd.toFixed(2)}</span>
                        <span class="duration">/ ${durationMonths} month${durationMonths > 1 ? 's' : ''}</span>
                    </div>
                </div>
                
                <div class="duration-selector">
                    <label>Duration:</label>
                    <select id="durationSelect" onchange="updatePaymentDuration('${productId}')">
                        <option value="1" ${durationMonths === 1 ? 'selected' : ''}>1 Month - $${product.priceUsd}</option>
                        <option value="3" ${durationMonths === 3 ? 'selected' : ''}>3 Months - $${(product.priceUsd * 3 * 0.9).toFixed(2)} (10% off)</option>
                        <option value="12" ${durationMonths === 12 ? 'selected' : ''}>12 Months - $${(product.priceUsd * 12 * 0.8).toFixed(2)} (20% off)</option>
                    </select>
                </div>
                
                <h4 class="payment-section-title">💳 Pay with Card</h4>
                <div class="payment-methods card-section">
                    <button class="payment-method-btn stripe" onclick="payWithStripe('${productId}')">
                        <span class="method-icon">💳</span>
                        <span class="method-name">Credit/Debit Card</span>
                        <span class="method-desc">Visa, Mastercard, Amex via Stripe</span>
                    </button>
                </div>
                
                <h4 class="payment-section-title">💰 Pay with Crypto</h4>
                <div class="crypto-chain-selector">
                    <label>Select Chain & Token:</label>
                    <div class="chain-options">
                        <div class="chain-group">
                            <div class="chain-header">◎ Solana</div>
                            <div class="token-buttons">
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'solana', 'SOL')">SOL</button>
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'solana', 'USDT')">USDT</button>
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'solana', 'USDC')">USDC</button>
                            </div>
                        </div>
                        <div class="chain-group">
                            <div class="chain-header">₿ Bitcoin</div>
                            <div class="token-buttons">
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'bitcoin', 'BTC')">BTC</button>
                            </div>
                        </div>
                        <div class="chain-group">
                            <div class="chain-header">Ξ Ethereum</div>
                            <div class="token-buttons">
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'ethereum', 'ETH')">ETH</button>
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'ethereum', 'USDT')">USDT</button>
                                <button class="token-btn" onclick="selectCryptoPayment('${productId}', 'ethereum', 'USDC')">USDC</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn-secondary" onclick="closePaymentChoiceModal()">Cancel</button>
            </div>
        </div>
    `;
    
    modal.classList.add('active');
}

/**
 * Handle crypto payment selection
 */
function selectCryptoPayment(productId, chain, token) {
    const duration = getDuration();
    closePaymentChoiceModal();
    initCryptoPayment(productId, duration, chain, token);
}

/**
 * Close payment choice modal
 */
function closePaymentChoiceModal() {
    const modal = document.getElementById('paymentChoiceModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

/**
 * Get selected duration
 */
function getDuration() {
    const select = document.getElementById('durationSelect');
    return parseInt(select?.value || '1', 10);
}

/**
 * Update payment duration display
 */
function updatePaymentDuration(addonId) {
    const duration = getDuration();
    showPaymentChoice(addonId, duration);
}

/**
 * Redirect to Stripe checkout
 */
async function payWithStripe(addonId) {
    const duration = getDuration();
    
    try {
        showToast('Redirecting to Stripe...', 'info');
        
        const response = await fetch('/api/stripe/checkout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                add_on: addonId,
                duration_months: duration
            })
        });
        
        const data = await response.json();
        
        if (data.checkout_url) {
            window.location.href = data.checkout_url;
        } else {
            throw new Error(data.error || 'Failed to create Stripe checkout');
        }
        
    } catch (error) {
        console.error('Stripe checkout error:', error);
        showToast('Failed to start Stripe checkout', 'error');
    }
}

// ============================================
// Utilities
// ============================================

/**
 * Show toast notification (uses Dashboard.showToast if available)
 */
function showToast(message, type = 'info') {
    if (typeof Dashboard !== 'undefined' && Dashboard.showToast) {
        Dashboard.showToast(message, type);
    } else {
        // Fallback toast implementation
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// ============================================
// Export for Global Access
// ============================================

window.CryptoPayment = {
    init: initCryptoPayment,
    showChoice: showPaymentChoice,
    verify: verifyTransaction,
    close: closeCryptoPaymentModal,
    config: CRYPTO_CONFIG
};
