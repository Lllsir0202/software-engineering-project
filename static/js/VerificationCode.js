let countdown = 60;  // 倒计时60秒
let timer = null;

function sendCode() {
    const email = document.getElementById('email').value;
    if(email == null) {
        alert("请填写邮箱");
        return;
    }
    const btn = document.getElementById('sendCodeBtn');
    btn.disabled = true;
    timer = setInterval(updateCountdown, 1000);
    fetch('http://localhost:5000/send_code', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `email=${encodeURIComponent(email)}`
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
        if (!data.success) {
            clearInterval(timer);
            btn.disabled = false;
            document.getElementById('countdown').textContent = '';
        }
    })
    .catch(error => {
        console.error('请求失败:', error);
    });
}

function updateCountdown() {
    countdown--;
    document.getElementById('countdown').textContent = `${countdown}秒后重试`;
    if (countdown <= 0) {
        clearInterval(timer);
        document.getElementById('sendCodeBtn').disabled = false;
        document.getElementById('countdown').textContent = '';
        countdown = 60;
    }
}