function sendCommand(clientId) {
    var cmd = document.getElementById('cmd-' + clientId).value;
    fetch('/send_command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'client_id=' + encodeURIComponent(clientId) + '&command=' + encodeURIComponent(cmd)
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('result').innerHTML = '<div class="alert alert-' + (data.status=='success'?'success':'danger') + '">' + data.message + '</div>';
    });
}

function fetchClients() {
    fetch('/api/clients')
        .then(r => r.json())
        .then(data => {
            let tbody = document.querySelector('#client-table-body');
            tbody.innerHTML = '';
            data.clients.forEach((c, idx) => {
                tbody.innerHTML += `
                <tr>
                    <td>${idx+1}</td>
                    <td>${c.hostname}</td>
                    <td>${c.last_seen}</td>
                    <td><input type="text" class="form-control form-control-sm command-input" id="cmd-${c.id}" placeholder="Komut yaz..."></td>
                    <td><button class="btn btn-sm btn-primary" onclick="sendCommand('${c.id}')">Gönder</button></td>
                </tr>
                `;
            });
        });
}

setInterval(fetchClients, 3000);
window.onload = fetchClients;
