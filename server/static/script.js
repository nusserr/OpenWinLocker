class ClientManager {
    constructor() {
        this.clients = [];
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.loadClients();
        this.setupModals();
    }

    bindEvents() {
        document.getElementById('refresh-btn').addEventListener('click', () => this.loadClients());
        document.getElementById('add-client-btn').addEventListener('click', () => this.showAddClientModal());
        document.getElementById('add-client-form').addEventListener('submit', (e) => this.handleAddClient(e));
        document.getElementById('edit-client-form').addEventListener('submit', (e) => this.handleEditClient(e));
    }

    setupModals() {
        // Add client modal
        const addModal = document.getElementById('add-client-modal');
        const addCloseBtn = addModal.querySelector('.close');
        const addCancelBtn = addModal.querySelector('.cancel-btn');

        addCloseBtn.addEventListener('click', () => this.hideAddClientModal());
        addCancelBtn.addEventListener('click', () => this.hideAddClientModal());
        window.addEventListener('click', (e) => {
            if (e.target === addModal) this.hideAddClientModal();
        });

        // Edit client modal
        const editModal = document.getElementById('edit-client-modal');
        const editCloseBtn = editModal.querySelector('.close');
        const editCancelBtn = editModal.querySelector('.cancel-btn');

        editCloseBtn.addEventListener('click', () => this.hideEditClientModal());
        editCancelBtn.addEventListener('click', () => this.hideEditClientModal());
        window.addEventListener('click', (e) => {
            if (e.target === editModal) this.hideEditClientModal();
        });
    }

    async loadClients() {
        try {
            const response = await fetch('/clients');
            const data = await response.json();
            this.clients = data.clients;
            this.updateStats();
            this.renderClients();
        } catch (error) {
            console.error('Error loading clients:', error);
            this.showError('Failed to load clients');
        }
    }

    updateStats() {
        const totalClients = this.clients.length;
        const unlockedClients = this.clients.filter(client => client.unlock_allowed).length;
        const lockedClients = totalClients - unlockedClients;

        document.getElementById('total-clients').textContent = totalClients;
        document.getElementById('unlocked-clients').textContent = unlockedClients;
        document.getElementById('locked-clients').textContent = lockedClients;
    }

    renderClients() {
        const tbody = document.getElementById('clients-tbody');
        tbody.innerHTML = '';

        if (this.clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-clients">No clients found</td></tr>';
            return;
        }

        this.clients.forEach(client => {
            const row = this.createClientRow(client);
            tbody.appendChild(row);
        });
    }

    createClientRow(client) {
        const row = document.createElement('tr');
        const statusClass = client.unlock_allowed ? 'status-unlocked' : 'status-locked';
        const statusText = client.unlock_allowed ? 'Unlocked' : 'Locked';
        const lastUpdated = client.last_updated ? new Date(client.last_updated).toLocaleString() : 'Never';

        row.innerHTML = `
            <td class="client-name">${client.name}</td>
            <td class="status ${statusClass}">${statusText}</td>
            <td class="timer">${this.formatTimer(client.youtube_timer_seconds)}</td>
            <td class="last-updated">${lastUpdated}</td>
            <td class="actions">
                <button class="btn btn-sm btn-toggle" onclick="clientManager.toggleUnlock('${client.name}')">
                    ${client.unlock_allowed ? 'Lock' : 'Unlock'}
                </button>
                <button class="btn btn-sm btn-edit" onclick="clientManager.showEditClientModal('${client.name}')">
                    Edit
                </button>
                <button class="btn btn-sm btn-delete" onclick="clientManager.deleteClient('${client.name}')">
                    Delete
                </button>
            </td>
        `;

        return row;
    }

    formatTimer(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    async toggleUnlock(clientName) {
        const client = this.clients.find(c => c.name === clientName);
        if (!client) return;

        try {
            const newStatus = !client.unlock_allowed;
            const response = await fetch(`/client/${clientName}/unlock-status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    client_name: clientName,
                    unlock_allowed: newStatus 
                })
            });

            if (response.ok) {
                await this.loadClients();
                this.showSuccess(`Unlock status updated for ${clientName}`);
            } else {
                throw new Error('Failed to update unlock status');
            }
        } catch (error) {
            console.error('Error toggling unlock:', error);
            this.showError('Failed to update unlock status');
        }
    }

    showAddClientModal() {
        document.getElementById('add-client-modal').style.display = 'block';
        document.getElementById('client-name').focus();
    }

    hideAddClientModal() {
        document.getElementById('add-client-modal').style.display = 'none';
        document.getElementById('add-client-form').reset();
    }

    async handleAddClient(e) {
        e.preventDefault();
        
        const clientName = document.getElementById('client-name').value.trim();
        const unlockAllowed = document.getElementById('unlock-status').value === 'true';
        const youtubeTimer = parseInt(document.getElementById('youtube-timer').value);

        if (!clientName) {
            this.showError('Client name is required');
            return;
        }

        try {
            // Configure client with all settings
            const response = await fetch(`/clients/${clientName}/configure`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    unlock_allowed: unlockAllowed,
                    youtube_timer_seconds: youtubeTimer
                })
            });

            if (response.ok) {
                this.hideAddClientModal();
                await this.loadClients();
                this.showSuccess(`Client ${clientName} added successfully`);
            } else {
                throw new Error('Failed to add client');
            }
        } catch (error) {
            console.error('Error adding client:', error);
            this.showError('Failed to add client');
        }
    }

    showEditClientModal(clientName) {
        const client = this.clients.find(c => c.name === clientName);
        if (!client) return;

        document.getElementById('edit-client-name').value = clientName;
        document.getElementById('edit-unlock-status').value = client.unlock_allowed.toString();
        document.getElementById('edit-youtube-timer').value = client.youtube_timer_seconds;
        
        document.getElementById('edit-client-modal').style.display = 'block';
    }

    hideEditClientModal() {
        document.getElementById('edit-client-modal').style.display = 'none';
        document.getElementById('edit-client-form').reset();
    }

    async handleEditClient(e) {
        e.preventDefault();
        
        const clientName = document.getElementById('edit-client-name').value;
        const unlockAllowed = document.getElementById('edit-unlock-status').value === 'true';
        const youtubeTimer = parseInt(document.getElementById('edit-youtube-timer').value);

        try {
            // Configure client with all settings
            const response = await fetch(`/clients/${clientName}/configure`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    unlock_allowed: unlockAllowed,
                    youtube_timer_seconds: youtubeTimer
                })
            });

            if (response.ok) {
                this.hideEditClientModal();
                await this.loadClients();
                this.showSuccess(`Client ${clientName} updated successfully`);
            } else {
                throw new Error('Failed to update client');
            }
        } catch (error) {
            console.error('Error updating client:', error);
            this.showError('Failed to update client');
        }
    }

    async deleteClient(clientName) {
        if (!confirm(`Are you sure you want to delete client "${clientName}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/client/${clientName}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                await this.loadClients();
                this.showSuccess(`Client ${clientName} deleted successfully`);
            } else {
                throw new Error('Failed to delete client');
            }
        } catch (error) {
            console.error('Error deleting client:', error);
            this.showError('Failed to delete client');
        }
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type) {
        // Remove existing notifications
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(n => n.remove());

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);

        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize the client manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.clientManager = new ClientManager();
});