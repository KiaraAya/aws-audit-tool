# ---------------------------------------------------------
# main_bot.py
# Entry point for the AWS Audit Tool Bot GUI
# ---------------------------------------------------------

from gui import AWSAuditToolGUI


def main():
    app = AWSAuditToolGUI()
    app.mainloop()


if __name__ == "__main__":
    main()