pipeline {
    agent any

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Mostrar contenido') {
            steps {
                sh 'pwd'
                sh 'ls -la'
            }
        }

    }
}
