
<img src="./resources/peoplejoin_designer.jpeg" alt="PeopleJoin" width="300">

## PeopleJoin

PEOPLEJOIN is a benchmark for evaluating LM-mediated collaborative problem solving. Given a user request, PEOPLEJOIN agents must identify teammates who might be able to assist, converse with these teammates to gather information, and finally compile a useful answer or summary for the original user. PEOPLEJOIN comprises two evaluation domains: PEOPLEJOIN-QA, focused on questions about tabular data, and PEOPLEJOIN-DOCCREATION, focused on document creation tasks. The two domains are adapted from existing NLP benchmarks for database question answering and multi-document summarization; here, however, the information needed to complete these tasks is distributed across synthetic “organizations” of 2–20 users, simulating natural multi-user collaboration scenarios. We implemented several popular LM agent architectures, and report their accuracy and efficiency at completing tasks.


## Setup

### Back-end Server

1. Install Python 3.11.
   One way is to use [pyenv](https://github.com/pyenv/pyenv) (for Linux/MacOS) or [pyenv-win](https://github.com/pyenv-win/pyenv-win#quick-start) (for Windows).
   Run `pyenv install --list | grep '^ *3.11' | tail -n1` to discover the most recent minor version of Python 3.11.
   For Windows run `pyenv install --list` and manually check the latest minor version of Python 3.11.
   Run `pyenv install 3.11.X` where `X` is the latest minor version available.
1. Install [Poetry](https://python-poetry.org/) 1.5 or later following the [instructions](https://python-poetry.org/docs/#installation).
   On Windows, you can use the following command in Powershell: `(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python`.
1. Configure Poetry to use your Python 3.11 installation.
    - If using `pyenv` setup above: run `poetry env use $(pyenv prefix 3.11.X)/bin/python`
    - Otherwise: run `poetry env use <path to your Python 3.11 binary>`
1. Run `poetry install` to install the dependencies.
1. Run `poetry shell` to activate the venv.
1. Run `make backend` to start a back-end server at `http://127.0.0.1:8000/`.
    - To utilize Make file in Windows, you will have to install make on Windows. One way to do that is through chocolatey.
    - To install chocolatey, run the following command in the administrative PowerShell:
   `Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))`
    - Once installed, restart Powershell and run: `choco install make`. You can verify your installation using `make -v`.
    - You can provide config name such as `make backend AGENT_CONF=src/async_collab/scenarios/people_join_qa/agent_configs/spider_sample.json`


## Experimentation
- Make any changes to the LLM APi interface as needed in `src/async_collab/llm/llm_client_service.py`. 
- See `workspace/` for experiments scripts

## Project structure
- `src/`: Python code for the project.
- `tests/`: Unit tests for code in `src/`.
- `data/`: Releant data files


## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.


## Citation
```
@misc{jhamtani2025peoplejoin,
      title={LM Agents for Coordinating Multi-User Information Gathering}, 
      author={Harsh Jhamtani and Jacob Andreas and Benjamin Van Durme},
      year={2025}
}
```
<!-- Test line for testing push permissions -->
