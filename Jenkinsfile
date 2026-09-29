pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Tests') {
            steps {
                // The core, the local assistant and auth need only the standard
                // library. The UI tests run too if streamlit is installed on the
                // agent, and are skipped otherwise.
                sh 'python3 -m unittest discover -s tests -v'
            }
        }

    }
}
