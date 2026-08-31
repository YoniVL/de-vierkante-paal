plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.0.21" apply false
    id("com.chaquo.python") version "17.0.0" apply false
}

// Build-uitvoer buiten OneDrive houden: OneDrive lockt bestanden en dan kan
// Gradle/Chaquopy z'n mappen niet meer verwijderen.
val buildRoot = File(System.getProperty("user.home"), "dvp-android-build")
allprojects {
    val sub = path.replace(":", "/").removePrefix("/").ifEmpty { "root" }
    layout.buildDirectory.set(File(buildRoot, sub))
}
