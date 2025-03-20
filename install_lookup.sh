#!/bin/zsh

# Step 1: Create ~/bin directory if it doesn't exist
mkdir -p ~/bin

# Step 2: Copy the "lookup" file from the current working directory to ~/bin
cp ./lookup ~/bin/

# Step 3: Add ~/bin to .zshrc if it's not already there
if ! grep -q 'export PATH="$HOME/bin:$PATH"' ~/.zshrc; then
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
    echo "Added ~/bin to your PATH in .zshrc"
else
    echo "~/bin is already in your PATH in .zshrc"
fi

# Optional: Inform the user to reload .zshrc
echo "Please run 'source ~/.zshrc' to apply the changes."

