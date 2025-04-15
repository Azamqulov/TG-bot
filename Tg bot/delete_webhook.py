import requests

TOKEN = '7887218481:AAFVnjoAhAQRR2yLM3cM_J5ryBXCIfIjjP4'  # Bot tokenini kiriting

# Webhookni o‘chirish
url = f'https://api.telegram.org/bot{TOKEN}/deleteWebhook'
response = requests.get(url)

# Javobni tekshirish
if response.status_code == 200:
    print("Webhook muvaffaqiyatli o'chirildi!")
else:
    print("Webhook o'chirishda xatolik yuz berdi:", response.text)
