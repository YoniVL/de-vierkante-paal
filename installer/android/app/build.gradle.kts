plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

// Ondertekening: één vaste sleutel zodat updates over een oudere versie
// heen installeren. Ontbreekt de keystore, dan valt de release-build terug
// op de debug-sleutel (dan moet je bij een update wel eerst deïnstalleren).
val keystoreFile = rootProject.file("keystore/dvp-release.jks")

android {
    namespace = "be.devierkantepaal.tool"
    compileSdk = 34
    buildToolsVersion = "36.0.0"

    defaultConfig {
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"
        ndk {
            abiFilters += listOf("x86_64", "arm64-v8a")
        }
    }

    flavorDimensions += "merk"
    productFlavors {
        create("dvp") {
            dimension = "merk"
            applicationId = "be.devierkantepaal.tool"
        }
        create("aftrap") {
            dimension = "merk"
            applicationId = "be.aftrap.tool"
        }
    }

    signingConfigs {
        if (keystoreFile.exists()) {
            create("release") {
                storeFile = keystoreFile
                storePassword = "dvptool"
                keyAlias = "dvp"
                keyPassword = "dvptool"
            }
        }
    }

    buildTypes {
        getByName("debug") {
            isMinifyEnabled = false
        }
        getByName("release") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
                ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

chaquopy {
    defaultConfig {
        // 3.12: Chaquopy heeft prebuilt wheels (o.a. markupsafe) t.e.m. 3.13,
        // niet voor 3.14. buildPython = de losse Python 3.12 op deze pc.
        version = "3.12"
        val py312 = File(
            System.getProperty("user.home"),
            "AppData/Local/Programs/Python/Python312/python.exe"
        )
        if (py312.exists()) buildPython(py312.absolutePath)
        pip {
            install("jinja2")
            install("beautifulsoup4")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir(layout.buildDirectory.dir("generated/python"))
        }
        getByName("aftrap") {
            srcDir("src/aftrap/python")   // merk.json
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
}

// De dvp-broncode uit de repo naar een build-map kopiëren (niet in src/, dat
// verwart Gradle's taak-afhankelijkheidscontrole).
val kopieerDvp by tasks.registering(Sync::class) {
    from(rootProject.file("../../dvp")) {
        exclude("**/__pycache__/**", "**/*.pyc")
    }
    into(layout.buildDirectory.dir("generated/python/dvp"))
}
tasks.named("preBuild") { dependsOn(kopieerDvp) }
afterEvaluate {
    tasks.matching { it.name.matches(Regex("merge.*PythonSources")) }
        .configureEach { dependsOn(kopieerDvp) }
}
