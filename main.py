import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import logging
from functools import wraps

# === 1. Telegram bot token va admin ID ===
BOT_TOKEN = '7887218481:AAFVnjoAhAQRR2yLM3cM_J5ryBXCIfIjjP4'
ADMIN_IDS = [1685356708]  # o'z Telegram ID'ingni shu yerga yoz

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot yaratish
bot = telebot.TeleBot(BOT_TOKEN)

# === 2. Firebase konfiguratsiyasi ===
try:
    cred = credentials.Certificate('firebase-key.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logger.info("Firebase bilan muvaffaqiyatli bog'landi")
except Exception as e:
    logger.error(f"Firebase bog'lanishda xatolik: {e}")

# === 3. Admin uchun dekorator ===
def admin_required(func):
    @wraps(func)
    def wrapped(message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ Bu buyruq faqat adminlar uchun.")
            return
        return func(message, *args, **kwargs)
    return wrapped

# === 4. Asosiy buyruqlar ===
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    
    # Foydalanuvchini ma'lumotlar bazasiga qo'shish
    try:
        # Foydalanuvchi mavjud yoki yo'qligini tekshirish
        user_ref = db.collection('users').document(str(user_id))
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            # Yangi foydalanuvchi qo'shish
            user_ref.set({
                'username': username,
                'joined_date': datetime.datetime.now(),
                'is_active': True
            })
            logger.info(f"Yangi foydalanuvchi qo'shildi: {user_id} - {username}")
        
        # Asosiy menu
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton('📚 Kurslar')
        btn2 = types.KeyboardButton('📞 Aloqa')
        btn3 = types.KeyboardButton('ℹ️ Ma\'lumot')
        
        if message.from_user.id in ADMIN_IDS:
            btn_admin = types.KeyboardButton('👨‍💼 Admin panel')
            markup.add(btn1, btn2, btn3, btn_admin)
        else:
            markup.add(btn1, btn2, btn3)
        
        bot.send_message(message.chat.id, 
                        f"Assalomu alaykum, {message.from_user.first_name}! \n\nO'quv markazimiz botiga xush kelibsiz. Kerakli bo'limni tanlang:", 
                        reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Start buyrug'ida xatolik: {e}")
        bot.reply_to(message, "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

# === 5. Admin panel ===
@bot.message_handler(commands=['admin'])
@admin_required
def admin_panel(message):
    try:
        # Admin uchun klaviatura
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
        btn2 = types.InlineKeyboardButton("👥 O'quvchilar", callback_data="admin_students")
        btn3 = types.InlineKeyboardButton("💰 To'lovlar", callback_data="admin_payments")
        btn4 = types.InlineKeyboardButton("✉️ Xabar jo'natish", callback_data="admin_broadcast")
        markup.add(btn1, btn2, btn3, btn4)
        
        bot.send_message(message.chat.id, "👨‍💼 Admin panel. Kerakli bo'limni tanlang:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Admin panel xatoligi: {e}")
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# === 6. Tugmalar uchun callback handler ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
@admin_required
def admin_callback_handler(call):
    try:
        if call.data == "admin_stats":
            # Statistika ko'rsatish
            users_ref = db.collection('users')
            students_ref = db.collection('students')
            payments_ref = db.collection('payments')
            
            users_count = len(list(users_ref.stream()))
            students_count = len(list(students_ref.stream()))
            
            # Jami to'lovlar
            total_payments = 0
            for payment_doc in payments_ref.stream():
                payment_data = payment_doc.to_dict()
                total_payments += payment_data.get('amount', 0)
            
            stats_text = f"📊 Umumiy statistika:\n\n"
            stats_text += f"👤 Foydalanuvchilar: {users_count} ta\n"
            stats_text += f"👥 O'quvchilar: {students_count} ta\n"
            stats_text += f"💰 Jami to'lovlar: {total_payments:,} so'm\n"
            
            bot.edit_message_text(chat_id=call.message.chat.id, 
                                 message_id=call.message.message_id, 
                                 text=stats_text, 
                                 reply_markup=get_back_to_admin_markup())
        
        elif call.data == "admin_students":
            # O'quvchilar ro'yxati
            students_ref = db.collection('students')
            students = list(students_ref.stream())
            
            if not students:
                bot.edit_message_text(chat_id=call.message.chat.id, 
                                     message_id=call.message.message_id, 
                                     text="O'quvchilar mavjud emas", 
                                     reply_markup=get_back_to_admin_markup())
                return
            
            student_text = f"👥 O'quvchilar ro'yxati ({len(students)} ta):\n\n"
            
            for i, student_doc in enumerate(students[:10], 1):  # Faqat birinchi 10 ta ko'rsatiladi
                student_data = student_doc.to_dict()
                student_text += f"{i}. {student_data.get('name', 'Nomalum')}\n"
                student_text += f"   📱 Tel: {student_data.get('phone', 'Noma\'lum')}\n"
                student_text += f"   📚 Kurs: {student_data.get('course', 'Noma\'lum')}\n\n"
            
            if len(students) > 10:
                student_text += f"... va yana {len(students) - 10} ta o'quvchi"
            
            bot.edit_message_text(chat_id=call.message.chat.id, 
                                 message_id=call.message.message_id, 
                                 text=student_text, 
                                 reply_markup=get_back_to_admin_markup())
        
        elif call.data == "admin_payments":
            # To'lovlar
            payments_ref = db.collection('payments')
            payments = list(payments_ref.stream())
            
            if not payments:
                bot.edit_message_text(chat_id=call.message.chat.id, 
                                     message_id=call.message.message_id, 
                                     text="To'lovlar mavjud emas", 
                                     reply_markup=get_back_to_admin_markup())
                return
            
            payment_text = f"💰 To'lovlar ro'yxati ({len(payments)} ta):\n\n"
            
            total = 0
            for i, payment_doc in enumerate(payments[:10], 1):  # Faqat birinchi 10 ta ko'rsatiladi
                payment_data = payment_doc.to_dict()
                amount = payment_data.get('amount', 0)
                total += amount
                
                payment_text += f"{i}. {payment_data.get('student_name', 'Noma\'lum')}\n"
                payment_text += f"   💵 Summa: {amount:,} so'm\n"
                payment_text += f"   📅 Sana: {payment_data.get('date', 'Noma\'lum')}\n\n"
            
            payment_text += f"💰 Jami: {total:,} so'm\n"
            
            if len(payments) > 10:
                payment_text += f"... va yana {len(payments) - 10} ta to'lov"
            
            bot.edit_message_text(chat_id=call.message.chat.id, 
                                 message_id=call.message.message_id, 
                                 text=payment_text, 
                                 reply_markup=get_back_to_admin_markup())
        
        elif call.data == "admin_broadcast":
            # Xabar jo'natish
            bot.edit_message_text(chat_id=call.message.chat.id, 
                                 message_id=call.message.message_id, 
                                 text="✉️ Jo'natmoqchi bo'lgan xabarni yuboring. Bekor qilish uchun /cancel buyrug'ini yuboring.")
            
            bot.register_next_step_handler(call.message, process_broadcast_message)
        
        elif call.data == "admin_back":
            # Admin panelga qaytish
            admin_panel(call.message)
            
    except Exception as e:
        logger.error(f"Admin callback xatoligi: {e}")
        bot.send_message(call.message.chat.id, f"Xatolik yuz berdi: {e}")

# Admin panelga qaytish tugmasi
def get_back_to_admin_markup():
    markup = types.InlineKeyboardMarkup()
    btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")
    markup.add(btn_back)
    return markup

# Broadcast xabarni qayta ishlash
def process_broadcast_message(message):
    if message.text == '/cancel':
        bot.reply_to(message, "Xabar jo'natish bekor qilindi.")
        return
    
    try:
        users_ref = db.collection('users')
        users = list(users_ref.stream())
        
        sent_count = 0
        error_count = 0
        
        # Foydalanuvchilarga xabar jo'natish
        for user_doc in users:
            try:
                user_data = user_doc.to_dict()
                user_id = int(user_doc.id)
                
                if user_data.get('is_active', False):
                    bot.send_message(user_id, message.text)
                    sent_count += 1
            except Exception:
                error_count += 1
        
        # Adminlarga natija haqida xabar berish
        bot.reply_to(message, f"✅ Xabar {sent_count} ta foydalanuvchiga jo'natildi.\n❌ {error_count} ta foydalanuvchiga jo'natishda xatolik.")
        
    except Exception as e:
        logger.error(f"Broadcast xatoligi: {e}")
        bot.reply_to(message, f"Xatolik yuz berdi: {e}")

# === 7. Text message handler ===
@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text
    
    if text == '📚 Kurslar':
        courses_menu(message)
    elif text == '📞 Aloqa':
        contact_menu(message)
    elif text == 'ℹ️ Ma\'lumot':
        about_menu(message)
    elif text == '👨‍💼 Admin panel' and message.from_user.id in ADMIN_IDS:
        admin_panel(message)
    else:
        bot.reply_to(message, "Tushunarsiz buyruq. Iltimos, menyudan tanlang.")

# === 8. Kurslar bo'limi ===
def courses_menu(message):
    try:
        courses_ref = db.collection('courses')
        courses = list(courses_ref.stream())
        
        if not courses:
            bot.send_message(message.chat.id, "Hozirda kurslar mavjud emas.")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for course_doc in courses:
            course_data = course_doc.to_dict()
            course_name = course_data.get('name', 'Noma\'lum kurs')
            btn = types.InlineKeyboardButton(course_name, callback_data=f"course_{course_doc.id}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, "📚 Mavjud kurslar:", reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Kurslar menyusida xatolik: {e}")
        bot.send_message(message.chat.id, "Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

# === 9. Aloqa bo'limi ===
def contact_menu(message):
    contact_text = "📞 Biz bilan bog'lanish:\n\n"
    contact_text += "📱 Telefon: +998 XX XXX XX XX\n"
    contact_text += "📍 Manzil: Toshkent sh., ...\n"
    contact_text += "⏰ Ish vaqti: 9:00 - 18:00\n\n"
    contact_text += "🔗 Ijtimoiy tarmoqlar:\n"
    contact_text += "Telegram: @username\n"
    contact_text += "Instagram: @username"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_register = types.InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="register")
    markup.add(btn_register)
    
    bot.send_message(message.chat.id, contact_text, reply_markup=markup)

# === 10. Ma'lumot bo'limi ===
def about_menu(message):
    about_text = "ℹ️ Biz haqimizda:\n\n"
    about_text += "O'quv markazimiz 20XX-yildan beri faoliyat yuritib kelmoqda. "
    about_text += "Biz zamonaviy ta'lim metodikalarini qo'llab, sifatli ta'lim beramiz.\n\n"
    about_text += "🏆 Bizning yutuqlarimiz:\n"
    about_text += "- 1000+ bitiruvchilar\n"
    about_text += "- 50+ malakali o'qituvchilar\n"
    about_text += "- 20+ yo'nalishlar"
    
    bot.send_message(message.chat.id, about_text)

# === 11. Ro'yxatdan o'tish ===
@bot.callback_query_handler(func=lambda call: call.data == "register")
def register_callback(call):
    bot.edit_message_text(chat_id=call.message.chat.id,
                         message_id=call.message.message_id,
                         text="📝 Ro'yxatdan o'tish uchun ismingizni kiriting:")
    
    bot.register_next_step_handler(call.message, process_name)

# Ro'yxatdan o'tish jarayonlari
def process_name(message):
    user_id = message.from_user.id
    db.collection('registration_temp').document(str(user_id)).set({
        'name': message.text,
        'timestamp': datetime.datetime.now()
    })
    
    bot.reply_to(message, "📱 Telefon raqamingizni kiriting (masalan, +998XX XXXXXXX):")
    bot.register_next_step_handler(message, process_phone)

def process_phone(message):
    user_id = message.from_user.id
    
    # Telefon raqamni saqlash
    db.collection('registration_temp').document(str(user_id)).update({
        'phone': message.text
    })
    
    # Kurslarni olish
    courses_ref = db.collection('courses')
    courses = list(courses_ref.stream())
    
    if not courses:
        process_course(message, "Boshqa")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    for course_doc in courses:
        course_data = course_doc.to_dict()
        course_name = course_data.get('name', 'Noma\'lum kurs')
        markup.add(types.KeyboardButton(course_name))
    
    markup.add(types.KeyboardButton("Boshqa"))
    
    bot.reply_to(message, "📚 Qaysi kursga yozilmoqchisiz?", reply_markup=markup)
    bot.register_next_step_handler(message, process_course)

def process_course(message, course_name=None):
    user_id = message.from_user.id
    
    # Kursni saqlash
    course = course_name if course_name else message.text
    
    try:
        # Vaqtinchalik ma'lumotlarni olish
        temp_ref = db.collection('registration_temp').document(str(user_id))
        temp_data = temp_ref.get().to_dict()
        
        if not temp_data:
            bot.send_message(message.chat.id, "Xatolik yuz berdi. Qayta ro'yxatdan o'ting.")
            return
        
        # O'quvchini saqlash
        student_data = {
            'name': temp_data.get('name'),
            'phone': temp_data.get('phone'),
            'course': course,
            'registration_date': datetime.datetime.now(),
            'user_id': user_id
        }
        
        db.collection('students').add(student_data)
        
        # Vaqtinchalik ma'lumotlarni o'chirish
        temp_ref.delete()
        
        # Admin(lar)ga xabar jo'natish
        admin_notification = f"🆕 Yangi o'quvchi ro'yxatdan o'tdi!\n\n"
        admin_notification += f"👤 Ism: {student_data['name']}\n"
        admin_notification += f"📱 Telefon: {student_data['phone']}\n"
        admin_notification += f"📚 Kurs: {student_data['course']}"
        
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, admin_notification)
            except Exception as e:
                logger.error(f"Adminga xabar jo'natishda xatolik: {e}")
        
        # Asosiy menyuga qaytish
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton('📚 Kurslar')
        btn2 = types.KeyboardButton('📞 Aloqa')
        btn3 = types.KeyboardButton('ℹ️ Ma\'lumot')
        
        if message.from_user.id in ADMIN_IDS:
            btn_admin = types.KeyboardButton('👨‍💼 Admin panel')
            markup.add(btn1, btn2, btn3, btn_admin)
        else:
            markup.add(btn1, btn2, btn3)
        
        bot.send_message(message.chat.id, 
                       "✅ Ro'yxatdan o'tish muvaffaqiyatli yakunlandi! Tez orada siz bilan bog'lanamiz.", 
                       reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Ro'yxatdan o'tishda xatolik: {e}")
        bot.send_message(message.chat.id, f"Xatolik yuz berdi: {e}")

# === 12. Kurs ma'lumotlari ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('course_'))
def course_details(call):
    course_id = call.data.split('_')[1]
    
    try:
        course_ref = db.collection('courses').document(course_id)
        course_data = course_ref.get().to_dict()
        
        if not course_data:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                 message_id=call.message.message_id,
                                 text="Kurs ma'lumotlari topilmadi.")
            return
        
        # Kurs haqida ma'lumot
        course_text = f"📚 {course_data.get('name', 'Noma\'lum kurs')}\n\n"
        course_text += f"📝 Tavsif: {course_data.get('description', 'Tavsif mavjud emas')}\n\n"
        course_text += f"⏱ Davomiyligi: {course_data.get('duration', 'Noma\'lum')}\n"
        course_text += f"💰 Narxi: {course_data.get('price', 0):,} so'm"
        
        # Tugmalar
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_register = types.InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="register")
        btn_back = types.InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_courses")
        markup.add(btn_register, btn_back)
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text=course_text,
                             reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Kurs ma'lumotlarida xatolik: {e}")
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text=f"Xatolik yuz berdi: {e}")

# === 13. Kurslar ro'yxatiga qaytish ===
@bot.callback_query_handler(func=lambda call: call.data == "back_to_courses")
def back_to_courses(call):
    try:
        courses_ref = db.collection('courses')
        courses = list(courses_ref.stream())
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for course_doc in courses:
            course_data = course_doc.to_dict()
            course_name = course_data.get('name', 'Noma\'lum kurs')
            btn = types.InlineKeyboardButton(course_name, callback_data=f"course_{course_doc.id}")
            markup.add(btn)
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text="📚 Mavjud kurslar:",
                             reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Kurslarga qaytishda xatolik: {e}")
        bot.edit_message_text(chat_id=call.message.chat.id,
                             message_id=call.message.message_id,
                             text=f"Xatolik yuz berdi: {e}")

# === 14. Error handler ===
@bot.message_handler(func=lambda message: True, content_types=['audio', 'photo', 'voice', 'video', 'document', 'location', 'contact', 'sticker'])
def default_handler(message):
    bot.reply_to(message, "Bu turdagi xabarlar qabul qilinmaydi. Iltimos, matn xabar yuboring yoki menyudan foydalaning.")

# === 15. Botni ishga tushirish ===
if __name__ == "__main__":
    try:
        logger.info("Bot ishga tushdi...")
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
