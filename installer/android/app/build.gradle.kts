import java.time.LocalDate

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

    val nu = LocalDate.now()
    defaultConfig {
        minSdk = 26
        targetSdk = 34
        // versiecode loopt op met de bouwdatum (nodig om updates te installeren)
        versionCode = (nu.year - 2025) * 10000 + nu.monthValue * 100 + nu.dayOfMonth
        versionName = nu.toString()
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
        // logo.png komt per variant uit de flavor-bronmap (main levert 'm niet;
        // zie de exclude in kopieerDvp), zodat er nooit twee kopieën botsen.
        getByName("dvp") {
            srcDir("src/dvp/python")      // dvp/static/logo.png (schild)
        }
        getByName("aftrap") {
            srcDir("src/aftrap/python")   // merk.json + dvp/static/logo.png (kruisje)
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
        exclude("static/logo.png")   // per flavor geleverd (src/{dvp,aftrap}/python)
        exclude("static/logo.ico")   // enkel voor de Windows-snelkoppeling, niet op Android
    }
    into(layout.buildDirectory.dir("generated/python/dvp"))
}
tasks.named("preBuild") { dependsOn(kopieerDvp) }
afterEvaluate {
    tasks.matching { it.name.matches(Regex("merge.*PythonSources")) }
        .configureEach { dependsOn(kopieerDvp) }
}
