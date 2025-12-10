from services.telegram import run_bot


def main():
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
