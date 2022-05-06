import sqlite3
from ast import literal_eval
import telebot
import pandas as pd
import re

TOKEN = "1234"
bot = telebot.TeleBot(TOKEN)

commands = {
    "new":"شروع پردازش جمله جدید",
    "pre":"ویرایش مراحل قبلی",
    "stat":"شمار جمله های پردازش شده",
    "des":"توضیح مراحل کار با بات",
    "help":"اطلاع از کامندهای موجود"
}


@bot.message_handler(commands=['help'])
def help(message):
    help_text = ''
    for key in commands:  # generate help text out of the commands dictionary defined at the top
        help_text += "/" + key + ": "
        help_text += commands[key] + "\n"
    bot.send_message(message.chat.id, help_text)


@bot.message_handler(commands=['des'])
def des(message):
    des = "در هر مرحله یک جمله به همراه لیست واژگان بیگانه‌ی آن به شما نمایش داده میشود. و شما با جایگزینی بهترین مترادف‌ها جمله‌ی جدیدی برای بات می‌فرستید"
    bot.send_message(message.chat.id, des)


@bot.message_handler(commands=['stat'])
def stat(message):
    try:
        user_id = message.chat.username
        connection = sqlite3.connect("loan_dataset.sqlite")
        c = connection.cursor()
        c.execute('select user_id from user where user_id = ?', (user_id, ))
        user_id = c.fetchall()[0][0]
        c.execute(
            '''
            select user_step from parallel_data where user_id = ?
            order by user_step desc limit 1
            ''', (user_id, )
        )
        user_step = c.fetchall()[0][0]
        bot.send_message(message.chat.id, f" شما تا کنون {user_step} جمله را ویرایش کرده‌اید. ")
    except:
        pass


@bot.message_handler(commands=['pre'])
def pre(message):
    try:
        user_id = message.chat.username
        connection = sqlite3.connect("loan_dataset.sqlite")
        c = connection.cursor()
        c.execute("select edit_step from user where user_id = ?", (message.chat.username, ))
        edit_step = c.fetchall()[0][0]
        print("edit_step : ", edit_step)
        c.execute(
            '''
            select user_step from parallel_data where user_id = ? 
            order by user_step desc limit 1
            ''', (user_id, )
        )
        user_step = c.fetchall()[0][0]
        if edit_step == 0:
            edit_step = user_step
        else:
            edit_step = edit_step - 1
        c.execute("update user set edit_step = ? where user_id = ?", (edit_step,user_id ))
        c.execute(
            '''
                select sent_id, s.sent, s.loan_list from parallel_data left join sents s on s.id = parallel_data.sent_id
                where user_id = ? and user_step = ?''', (user_id, edit_step))
        sent_id, sent, loan_list = c.fetchall()[0]
        loan_list = literal_eval(loan_list)
        c.execute(
            f'''
                update user set current_sent_id = ? where user_id = ?
            ''', (sent_id, user_id)
        )
        bot.send_chat_action(message.chat.id, "typing")
        connection.commit()
        print("loan_list : ", loan_list)
        syn_text = ''
        for keyy in loan_list:
            if keyy in loan_dict.keys():
                sent = re.sub(keyy, "<b><u>"+keyy+"</u></b>", sent)
                syn_text += keyy + ": "
                syn_text += ", ".join(loan_dict[keyy]) + "\n"
        c.execute("select sent_pair from parallel_data where sent_id = ?", (sent_id, ))
        last_ans = c.fetchall()[0][0]
        bot.send_message(message.chat.id, sent, parse_mode='HTML')
        bot.send_message(message.chat.id, syn_text)
        bot.send_message(message.chat.id, "پاسخ قبلی شما:")
        bot.send_message(message.chat.id, last_ans)
        bot.register_next_step_handler(message, store_sents_pair)
    except:
        bot.send_message(message.chat.id, "مشکلی در pre پیش آمد مجدد تلاش کنید.")


def store_sents_pair(message):
    if not message.text.startswith('/'):
        try:
            sent_pair = message.text
            user_id = message.chat.username
            connection = sqlite3.connect("loan_dataset.sqlite")
            c = connection.cursor()
            c.execute('''select current_sent_id, edit_step from user where user_id = ?''', (user_id,))
            sent_id, edit_step = c.fetchall()[0]

            if edit_step == 0:
                bot.send_chat_action(message.chat.id, "typing")
                c.execute(
                    '''select sent from sents where id = ?'''
                    , (sent_id,))
                sent = c.fetchall()[0][0]

                c.execute(
                    '''
                    select user_step from parallel_data where user_id = ? 
                    order by user_step desc limit 1
                    ''', (user_id, )
                )
                try:
                    user_step = c.fetchall()[0][0]
                    user_step = user_step + 1
                except:
                    user_step = 1
                c.execute(
                    '''
                        insert into parallel_data (sent_id, sent, sent_pair, user_id, user_step) 
                        values (?, ?, ?, ?, ?)
                    ''', (sent_id, sent, sent_pair, user_id, user_step)
                )
                c.execute('''update sents set checked = 1 where id = ?''', (sent_id, ))
                connection.commit()
                new(message)
            else:
                c.execute('''
                    update parallel_data set sent_pair = ? where user_id = ? and user_step = ?
                    ''', (message.text, user_id, edit_step))
                c.execute('''
                    update user set edit_step = 0 where user_id = ?
                    ''', (user_id, ))
                connection.commit()
                new(message)

        except:
            bot.send_message(message.chat.id, "مشکلی پیش‌ آمد مجدد تلاش کنید.")
    else:
        if message.text == "/pre":
            pre(message)
        elif message.text == "/new":
            new(message)
        elif message.text == "/stat":
            stat(message)
        elif message.text == "/help":
            help(message)
        else:
            bot.send_message(message.chat.id, "کامند اشتباه وارد کردی!")


@bot.message_handler(commands=['new'])
def new(message):
    try:
        user_id = message.chat.username
        connection = sqlite3.connect("loan_dataset.sqlite")
        c = connection.cursor()
        c.execute('select parcels from user where user_id = ?', (user_id, ))
        parcels = tuple(literal_eval(c.fetchall()[0][0]))
        c.execute(
            f'''
                select id, sent, loan_list 
                from sents where parcel in {parcels} and checked = 0
                order by random() limit 1
            '''
        )
        sent_id, sent, loan_list = c.fetchall()[0]
        loan_list = literal_eval(loan_list)
        c.execute(
            f'''
                update user set current_sent_id = ? where user_id = ?
            ''', (sent_id, user_id)
        )
        bot.send_chat_action(message.chat.id, "typing")
        connection.commit()
        syn_text = ''
        for key in loan_list:
            if key in loan_dict.keys():
                sent = re.sub(key, "<b><u>" + key + "</u></b>", sent)
                syn_text += key + ": "
                syn_text += ", ".join(loan_dict[key]) + "\n"

        bot.send_message(message.chat.id, syn_text)
        bot.send_message(message.chat.id, sent, parse_mode='HTML')
        bot.register_next_step_handler(message, store_sents_pair)

    except IndexError:
        bot.send_message(message.chat.id, "شما ثبت نام نشده‌اید!\nارتباط با ادمین @Fatemeh_Pasban")


if __name__ == '__main__':
    loan_dict_path = "new_balance_dict.xlsx"
    df_loan_dict = pd.read_excel(loan_dict_path)
    df_loan_dict["مترادف ها"] = df_loan_dict["مترادف ها"].apply(eval)
    loan_dict = dict(zip(df_loan_dict["واژه"], df_loan_dict["مترادف ها"]))

    bot.polling(none_stop=True)
