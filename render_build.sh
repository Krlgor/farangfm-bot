#!/bin/bash
# Устанавливаем Python 3.11 через pyenv
curl https://pyenv.run | bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
pyenv install 3.11.0
pyenv global 3.11.0

# Устанавливаем зависимости
pip install --upgrade pip
pip install -r requirements.txt