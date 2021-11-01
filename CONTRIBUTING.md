# Contributing to the project

To start with, thank you for taking the time to contribute! ❤️


## How to contribute to the project?
There are a lot of ways with which one can contribute to this project.
1. As a user of the project, if one comes across a certain discrepancy or if one wants a certain feature to be implemented, they can open up an issue ticket at https://github.com/CentOS/duffy/issues.
2. As a developer of the project, one can help with providing the code that helps fix a certain issue or helps attain a certain new feature by opening up a pull request against the primary branch.
3. As a user or developer of the project, one can help with documenting the ins and outs of the project with respect to its usage, development, contribution, maintenance, deployment etc.


## How to set up the development environment?
1. Fork the repository to your own GitHub namespace.
2. Clone the forked repository and navigate into the project directory.
   ```
   git clone https://github.com/<namespace>/duffy.git
   cd duffy
   ```
3. Set up and activate a virtual environment.
   * Using native virtual environment
     ```
     python3 -m venv duffyenv
     source duffyenv/bin/activate
     ```
   Or
   * Using virtualenv wrapper
     ```
     virtualenv duffyenv
     source duffyenv/bin/activate
     ```
   Or
   * Using Poetry virtual environment shell
     ```
     poetry shell
     ```
4. Install using Poetry
   ```
   poetry install
   ```
5. Checkout to a new branch with a clear descriptive name.
   ```
   git checkout -b <some-branch-name>
   ```
6. Open up the project in an IDE or a code-editor to start adding your contributions.
7. Test your changes by running the server using 
   ```
   duffy -p 8000 -4 -l trace
   ```
   1. Please choose a port number that you have the permissions for and is not already in use.
   2. Please make use of the variety of log levels in order to better facilitate the debugging process
      1. `critical` - Exhibit extremely severe error events, which may result in the application's termination
      2. `error` - Exhibit significant error events that will halt normal programme execution but may still allow the application to execute
      3. `warning` - Exhibit potentially dangerous circumstances that may be of interest to end users or system administrators and identify potential issues
      4. `info` - Exhibit informational messages that may be useful to end users and system administrators, as well as the application's progress
      5. `debug` - Exhibit application developers' usage of relatively detailed debugging
      6. `trace` - Exhibits all related messages.
8. Once done making the changes, be sure to add tests for the code and see if your code changes comply with them by running
   ```
   pytest
   ```
10. Please commit with a precise commit message and signature.
    ```
    git commit -sm "<some-commit-message-which-actually-makes-sense>"
    ```
11. Push your local commits to the remote branch of your fork.
    ```
    git push origin <some-branch-name>
    ```


## How do I contribute in the right way?
1. Please follow the following standard for your commit messages,
   1. Limit the subject line of a commit to 50 characters and the body of a commit to 72 characters.
   2. Use the imperative sense of a verb in the subject line (eg. Use `Update ...` and not `Updated ...`).
   3. Capitalize the subject line and do not use periods at the end of the sentence.
   4. Use the body to justify and describe the changes and start it after leaving a blank line under the subject.
   5. Be sure to sign your commits before pushing them to the remote branch of your fork.
2. For every code addition made to the project, 
   1. Add inline comments to the parts of the code which require additional context and add to the documentation as well.
   2. Ensure that the code is semantic and the names provided to variables, functions and classes describe their purpose.
   3. Tests must be added in the same pull request to ensure that a good coverage and great overall code quality.
   4. If there are parts in the code that do not require testing or cannot be tested, be sure to exclude them in the config.
   5. Use `black .` to format the code and `isort .` to automatically sort the imports before pushing the changes.


## Where do I reach out if I wish to discuss the project?
The current maintainers of the project are available at the #centos-ci IRC channel of libera.chat. Please feel free to reach out to them. As the team members hail from a various countries across the world, patience in waiting for a reply back is greatly appreciated. 
