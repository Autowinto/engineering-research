import os
import json
import re
import time
from groq import Groq

# Create a list of initial error types. Null pointer, etc.
# Load all errors into a dict with their commit message
# Iterate through the errors, send them to groq, and save the commit details with the response as an object in a list with the
# response as a key. Then save it all to a file.
# When groq is called provide the list of error types it can choose from, and let it know it can create a new one if it wishes.

# Initial error types
error_types = [
    "NullPointer",
    "ZeroDivision",
    "TypeError",
    "ValueError",
    "IndexError",
    "KeyError",
    "AttributeError",
]

api_keys = [
    "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",
    "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",
    "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",
    "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",
]


# Create a Groq client with rotating API keys
def get_client(api_key):
    return Groq(api_key=api_key)


# load data from commits_data folder, which is many json files, into a list of dicts


def load_data():
    data = []
    for file in os.listdir("commits_data"):
        with open(f"commits_data/{file}") as f:
            commits = json.load(f).get("commits", [])
            for commit in commits:
                data.append(
                    {
                        "message": commit["message"],
                        "changes": commit["changes"][0]["patch"],
                    }
                )
    return data


def clean_text(text):
    # Remove special characters and extra spaces
    return re.sub(r"\W+", " ", text).strip()


def query_llm(model, data):
    for key in api_keys:
        try:
            client = get_client(key)
            chat_completion = client.chat.completions.create(
                max_completion_tokens=30,
                messages=[
                    {
                        "role": "system",
                        "content": f"You will be provided a commit message and code changes. You must from this extract what kind of error was fixed in the code changes. You must answer with a single word, that describes the error. You will be provided with a list of errors to choose from, and can create your own if these do not fit. The error types are: {str(error_types)}",
                    },
                    {
                        "role": "user",
                        "content": f"Commit message: {data['message']}. Code changes: {data['changes']}",
                    },
                ],
                model=model,
            )
            return chat_completion
        except Exception as e:
            print(e)
            continue
    print("All API keys failed, waiting and retrying")
    time.sleep(60)
    return query_llm(model, data)


# function to run the llm, save results to a file with a specific name based on its model, and note the time it took to run
def run_llm(model):
    dataset = {}
    errors_too_long = []
    for data in load_data():
        chat_completion = query_llm(model, data)
        # Add the response to the list of error types, if it does not already exist there:
        error_type = clean_text(chat_completion.choices[0].message.content)
        if len(error_type) >= 30:
            # save the response to a list of errors that are too long
            errors_too_long.append(error_type)
            continue
        if error_type not in error_types:
            error_types.append(error_type)
            print("Error type added: ", error_type)

        # Add the commit data to the dataset dictionary
        if error_type not in dataset:
            dataset[error_type] = []
        dataset[error_type].append(
            {"message": clean_text(data["message"]), "changes": data["changes"]}
        )

        with open(f"results/{model}/errors.json", "w") as f:
            json.dump(dataset, f, indent=4)
        with open(f"results/{model}/errors_too_long.json", "w") as f:
            json.dump(errors_too_long, f, indent=4)


# call the function with the models and names
models = [
    "gemma2-9b-it",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama-guard-3-8b",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "qwen-qwq-32b",
    "mistral-saba-24b",
    "qwen-2.5-coder-32b",
    "qwen-2.5-32b",
    "deepseek-r1-distill-qwen-32b",
    "deepseek-r1-distill-llama-70b-specdec",
    "deepseek-r1-distill-llama-70b",
    "llama-3.3-70b-specdec",
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
]

os.makedirs("results", exist_ok=True)

for model in models:
    os.makedirs(f"results/{model}", exist_ok=True)
    start = time.time()

    run_llm(model)
    end = time.time()
    print(f"Model {model} took {end-start} seconds to run")
    # save time to a file
    with open(f"results/{model}/time.txt", "w") as f:
        f.write(f"Model {model} took {end-start} seconds to run")
