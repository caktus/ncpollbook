#!/bin/bash

if command -v op &> /dev/null; then
    echo $(op read --account caktusgroup.1password.com "op://ncpollbook/ncpollbook-vault-pass/notesPlain")
elif [[ ! -z "${ANSIBLE_VAULT_PASSWORD}" ]]; then
    echo $ANSIBLE_VAULT_PASSWORD
    >&2 echo "WARNING: You are using a deprecated method of storing the Ansible vault password. It will be removed in the future. Please unset ANSIBLE_VAULT_PASSWORD and install the 1Password CLI."
else
    echo "no password found"
    exit 1
fi
